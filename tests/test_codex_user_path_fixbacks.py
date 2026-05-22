from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PLUGIN_NAMESPACE = "codexscientist-codex"


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


def test_installer_registers_codex_mcp_server_and_keeps_install_tree_clean(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex_home = home / ".codex"
    agents_home = home / ".agents"
    env = os.environ.copy()
    env.update({"HOME": str(home), "CODEX_HOME": str(codex_home), "AGENTS_HOME": str(agents_home)})

    proc = _run(["bash", "scripts/install.sh"], env=env, timeout=120)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    config = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert '[plugins."codexscientist-codex@local-personal"]' in config
    assert "[mcp_servers.codexscientist-codex]" in config
    assert 'command = "python"' not in config
    assert ('command = "python3"' in config) or ('command = "' in config and "python" in config)
    assert 'args = ["-B",' in config
    assert "scripts/cs_mcp.py" in config
    marketplace = json.loads((agents_home / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    plugin_entry = next(item for item in marketplace["plugins"] if item["name"] == PLUGIN_NAMESPACE)
    assert plugin_entry["source"]["path"] == "./.codex/plugins/codexscientist-codex"
    assert "codex mcp list" in proc.stdout
    assert "csctl.py doctor" not in proc.stdout
    smoke_line = next(line for line in proc.stdout.splitlines() if "Smoke test:" in line)
    assert " -B " in smoke_line

    installed = codex_home / "plugins" / PLUGIN_NAMESPACE
    assert installed.exists()
    assert not list(installed.rglob("__pycache__"))
    assert not list(installed.rglob("*.pyc"))

    smoke_env = env.copy()
    smoke_env.pop("PYTHONDONTWRITEBYTECODE", None)
    smoke = _run([PYTHON, "-B", str(installed / "scripts" / "cs_mcp.py"), "--stdio-smoke", "call", "cs_doctor", "{}"], cwd=tmp_path, env=smoke_env)
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert not list(installed.rglob("__pycache__"))
    assert not list(installed.rglob("*.pyc"))


def test_init_project_writes_mcp_first_project_note(tmp_path: Path) -> None:
    project = tmp_path / "research-project"
    proc = _run(["bash", "scripts/init_project.sh", str(project)], timeout=60)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    note = (project / ".codex" / "CODEXSCIENTIST_CODEX.md").read_text(encoding="utf-8")
    assert "CodexScientist Codex MCP Project Note" in note
    assert "scripts/cs_mcp.py" in note
    assert "--stdio-smoke initialize" in note
    assert "--stdio-smoke tools/list" in note
    assert "cs_doctor" in note
    assert "No MCP transport is used" not in note
    assert "Native control script" not in note
    assert "scripts/csctl.py" not in note


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
        "cs_goal_context",
        "No MCP transport is used",
        "Native control script",
        "csctl.py doctor",
        "MCP registration snippet",
        "Use hidden admin/debug CLI",
    ]
    for phrase in forbidden:
        assert phrase not in combined

    assert "default core profile exposes 11" in combined
    assert "evidence" in combined and "formal_run" in combined
    assert "stage is a label" in combined or "stage label" in combined
    assert "codex mcp add codexscientist-codex" in combined
    manual_lines = [line.strip() for line in combined.splitlines() if line.strip().startswith("codex mcp add codexscientist-codex")]
    assert manual_lines
    for line in manual_lines:
        assert "-- python -B " in line or "-- python3 -B " in line, line


def test_public_plugin_metadata_and_packaged_support_skills_are_codex_neutral() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    encoded_manifest = json.dumps(manifest, ensure_ascii=False)
    assert "Hermes" not in encoded_manifest
    assert "hermes" not in encoded_manifest.lower()

    packaged_roots = [
        ROOT / "skills",
        ROOT / "codex_scientist" / "runtime" / "resources" / "skills",
        ROOT / "codex_scientist" / "runtime" / "resources" / "repo" / "src" / "skills",
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
                if any(token in line for token in ("Hermes", ".hermes", "scripts/csctl.py", "csctl.py")):
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
    assert "MCP-only default" in joined
    assert "`/goal` is Codex-native" in joined
    assert "does not implement slash commands" in joined


def test_packaged_skill_names_fit_codex_namespace_limit() -> None:
    offenders: list[str] = []
    for skill_path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        name = _frontmatter_name(skill_path)
        namespaced = f"{PLUGIN_NAMESPACE}:{name}"
        if len(namespaced) > 64:
            offenders.append(f"{skill_path.relative_to(ROOT)} -> {namespaced} ({len(namespaced)})")
    assert not offenders


def test_router_skill_default_flow_uses_visible_profile_tools_not_hidden_skill_helpers() -> None:
    text = (ROOT / "skills" / "codexscientist-codex" / "SKILL.md").read_text(encoding="utf-8")

    assert "cs_skill_search" not in text
    assert "cs_skill_load" not in text
    assert "cs_status" in text and "cs_doctor" in text
    assert "cs_new_quest" in text and "cs_record_user_requirement" in text
    assert "evidence" in text and "formal_run" in text and "literature" in text and "paper_write" in text


def test_analysis_campaign_creator_is_visible_when_slice_recorder_is_visible() -> None:
    for profile in ("evidence", "formal_run"):
        payload = tools_list_payload({"profile": profile})
        assert payload["ok"] is True, payload
        names = {tool["name"] for tool in payload["tools"]}
        assert "cs_record_analysis_slice" in names
        assert "cs_create_analysis_campaign" in names
        assert "cs_get_analysis_campaign" in names


def test_bash_exec_schema_exposes_formal_run_provenance_fields() -> None:
    payload = call_tool("cs_tool_schema", {"name": "cs_bash_exec"})

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
    proc = _run([PYTHON, "scripts/cs_mcp.py", "--stdio-smoke", "tools/list", '{"profile":"evidence"}'])

    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True, payload
    assert payload["profile"] == "evidence"
    names = {tool["name"] for tool in payload["tools"]}
    assert "cs_create_analysis_campaign" in names
    assert "cs_record_analysis_slice" in names
