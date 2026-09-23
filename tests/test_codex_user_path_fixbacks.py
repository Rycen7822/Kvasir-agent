from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from kvasir_agent.mcp.tool_registry import call_tool, tools_list_payload

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PLUGIN_NAMESPACE = "kvasir-agent"


def _run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def _frontmatter_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    frontmatter = text.split("---", 2)[1]
    for line in frontmatter.splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing frontmatter name in {path}")


def test_installer_delegates_exact_reference_and_propagates_failures(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "args.json"
    codex = bin_dir / "codex"
    codex.write_text(f"#!{PYTHON}\nimport json, os, sys\nfrom pathlib import Path\nPath(os.environ['CAPTURE_ARGS']).write_text(json.dumps(sys.argv[1:]))\nsys.exit(int(os.environ.get('CODEX_TEST_EXIT', '0')))\n")
    codex.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'], CAPTURE_ARGS=str(capture))
    proc = _run(["bash", "scripts/install.sh", "kvasir-agent@test-market"], env=env)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(capture.read_text()) == ["plugin", "add", "kvasir-agent@test-market"]
    assert "new Codex thread" in proc.stdout
    env["CODEX_TEST_EXIT"] = "7"
    failed = _run(["bash", "scripts/install.sh", "kvasir-agent@test-market"], env=env)
    assert failed.returncode == 7
    assert "new Codex thread" not in failed.stdout
    capture.unlink()
    invalid = _run(["bash", "scripts/install.sh"], env=env)
    assert invalid.returncode == 2
    assert not capture.exists()


def test_init_project_writes_mcp_first_project_note(tmp_path: Path) -> None:
    project = tmp_path / "research-project"
    proc = _run(["bash", "scripts/init_project.sh", str(project)], timeout=60)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    note = (project / ".codex" / "KVASIR_AGENT_CODEX.md").read_text(encoding="utf-8")
    assert "Kvasir-agent Codex MCP Project Note" in note
    assert "scripts/ka_mcp.py" in note
    assert "--stdio-smoke initialize" in note
    assert "--stdio-smoke tools/list" in note
    assert "ka_doctor" in note
    assert "No MCP transport is used" not in note
    assert "Native control script" not in note
    assert "scripts/kactl.py" not in note


def test_user_entry_docs_have_current_upgrade6_profile_contract() -> None:
    doc_paths = [
        "README.md",
        "README.zh-CN.md",
        "docs/INSTALL.md",
        "docs/MCP.md",
        "docs/ARCHITECTURE.md",
        "docs/MCP_CONTEXT_BUDGET.md",
        "docs/USAGE.md",
    ]
    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in doc_paths)
    forbidden = [
        "core profile: 14 tools",
        "goal profile: 47 tools",
        "active stage subset",
        "ka_goal_context",
        "No MCP transport is used",
        "Native control script",
        "kactl.py doctor",
        "MCP registration snippet",
        "Use hidden admin/debug CLI",
    ]
    for phrase in forbidden:
        assert phrase not in combined

    assert "24 public research tools" in combined
    assert "optional" in combined and "parameter schemas" in combined
    assert "codex plugin add" in combined
    assert "codex mcp remove kvasir-agent" in combined


def test_public_plugin_metadata_and_packaged_support_skills_are_codex_neutral() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    encoded_manifest = json.dumps(manifest, ensure_ascii=False)
    assert "Hermes" not in encoded_manifest
    assert "hermes" not in encoded_manifest.lower()

    packaged_roots = [
        ROOT / "skills",
        ROOT / "kvasir_agent" / "runtime" / "resources" / "skills",
        ROOT / "kvasir_agent" / "runtime" / "resources" / "repo" / "src" / "skills",
    ]
    text_suffixes = {".md", ".txt", ".yaml", ".yml", ".py", ".json", ".toml"}
    offenders: list[str] = []
    for root in packaged_roots:
        for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in text_suffixes):
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if stripped in {"metadata:", "hermes:"}:
                    continue
                if any(token in line for token in ("Hermes", ".hermes", "scripts/kactl.py", "kactl.py")):
                    offenders.append(f"{path.relative_to(ROOT)}:{line_no}: {stripped}")
    assert offenders == []


def test_manifest_default_prompts_fit_codex_plugin_limits() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    prompts = manifest["interface"].get("defaultPrompt")

    assert isinstance(prompts, list)
    assert 1 <= len(prompts) <= 3
    for prompt in prompts:
        assert isinstance(prompt, str)
        assert 1 <= len(prompt) <= 128
    joined = "\n".join(prompts)
    assert "Codex owns /goal" in joined
    assert "ka_research_read" in joined
    assert "operation=resume" in joined
    assert "scientific verification" in joined


def test_packaged_skill_names_fit_codex_namespace_limit() -> None:
    offenders: list[str] = []
    for skill_path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        name = _frontmatter_name(skill_path)
        namespaced = f"{PLUGIN_NAMESPACE}:{name}"
        if len(namespaced) > 64:
            offenders.append(f"{skill_path.relative_to(ROOT)} -> {namespaced} ({len(namespaced)})")
    assert not offenders


def test_router_skill_default_flow_uses_visible_profile_tools_not_hidden_skill_helpers() -> None:
    text = (ROOT / "skills" / "kvasir-agent" / "SKILL.md").read_text(encoding="utf-8")

    assert "ka_skill_search" not in text
    assert "ka_skill_load" not in text
    assert "ka_research_read" in text and "ka_research_read" in text
    assert "ka_new_quest" not in text
    assert "ka_record_user_requirement" in text
    assert "first write initializes" in text
    assert "parameter schemas" in text and "profiles are optional" in text


def test_analysis_campaign_creator_is_visible_when_slice_recorder_is_visible() -> None:
    for profile in ("evidence", "formal_run"):
        payload = tools_list_payload({"profile": profile})
        assert payload["ok"] is True, payload
        names = {tool["name"] for tool in payload["tools"]}
        assert "ka_analysis" in names
        assert "ka_analysis" in names
        assert "ka_analysis" in names


def test_bash_exec_schema_exposes_formal_run_provenance_fields() -> None:
    payload = call_tool("ka_tool_schema", {"name": "ka_bash_exec"})

    assert payload["ok"] is True, payload
    schema = payload["schema"]["input_schema"]
    properties = schema["properties"]
    for field in [
        "command_class",
        "provenance_reason",
        "experiment_or_artifact_id",
        "cwd_policy",
        "expected_outputs",
        "evidence_paths",
    ]:
        assert field in properties
    description = payload["schema"]["description"] + "\n" + json.dumps(properties, ensure_ascii=False)
    assert "operation=run" in description
    assert "formal" in description.lower()


def test_stdio_smoke_tools_list_accepts_profile_json_argument() -> None:
    proc = _run([PYTHON, "scripts/ka_mcp.py", "--stdio-smoke", "tools/list", '{"profile":"evidence"}'])

    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True, payload
    assert payload["profile"] == "evidence"
    names = {tool["name"] for tool in payload["tools"]}
    assert "ka_analysis" in names
    assert "ka_analysis" in names
