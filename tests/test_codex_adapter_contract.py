from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parent
PYTHON = sys.executable


def run_kactl(*args: str, project_root: Path | None = None) -> dict:
    env = os.environ.copy()
    if project_root is not None:
        env["KVASIR_AGENT_PROJECT_ROOT"] = str(project_root)
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "kactl.py"), *args],
        cwd=str(project_root or PLUGIN_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_codex_manifest_declares_mcp_only_default_and_hidden_admin_cli_boundary():
    manifest_path = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_text = json.dumps(manifest, ensure_ascii=False)
    assert manifest["name"] == "kvasir-agent"
    assert manifest["skills"] == "./skills"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert "MCP-only default" in manifest_text
    assert "`/goal` is Codex-native" in manifest_text
    assert "does not implement slash commands" in manifest_text
    assert "scripts/ka_mcp.py" in manifest_text
    assert "scripts/kactl.py" not in manifest_text
    assert "CLI fallback" not in manifest_text


def test_kactl_exposes_root_bound_public_schema_set():
    sys.path.insert(0, str(PLUGIN_ROOT))
    from kvasir_agent.runtime import schemas

    payload = run_kactl("list-tools", "--format", "json")
    names = {item["name"] for item in payload["tools"]}
    expected = {schema["name"] for schema in schemas.PUBLIC_SCHEMAS}
    hidden = {schema["name"] for schema in schemas.LEGACY_ONLY_SCHEMAS}
    assert payload["ok"] is True
    assert expected <= names
    assert names.isdisjoint(hidden)
    assert payload["transport"] == "codex-native-cli"
    assert payload["mcp"] is False


def test_kactl_public_tools_are_canonical_ka_surface():
    payload = run_kactl("list-tools", "--format", "json")
    names = {item["name"] for item in payload["tools"]}
    assert payload["ok"] is True
    assert payload["transport"] == "codex-native-cli"
    assert payload["mcp"] is False
    assert "ka_events" in names
    assert "ka_environment_validate" in names
    assert "ka_trajectory_show" in names
    assert "ka_feedback_ingest" in names
    assert not any(name.startswith("kvasiragent_") for name in names)
    assert payload["count"] == len(names)

    schema_payload = run_kactl("schema", "--format", "json")
    schema_names = {schema["name"] for schema in schema_payload["schemas"]}
    assert "ka_events" in schema_names
    assert not any(name.startswith("kvasiragent_") for name in schema_names)


def test_legacy_kvasiragent_aliases_are_not_public_default_surface():
    payload = run_kactl("list-tools", "--format", "json")
    names = {item["name"] for item in payload["tools"]}
    assert payload["ok"] is True
    assert not any(name.startswith("kvasiragent_") for name in names)
    assert not any(name.startswith("d" + "s_") for name in names)
    assert "ka_get_quest_state" not in names
    assert "ka_new_quest" not in names
    assert "ka_set_active_quest" not in names


def test_kactl_doctor_uses_vendored_runtime_without_external_ds(tmp_path: Path):
    payload = run_kactl("doctor", "--format", "json", project_root=tmp_path)
    assert payload["ok"] is True
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["vendored_runtime_import"]["ok"] is True
    assert checks["no_external_upstream_cli_required"]["ok"] is True
    assert str(tmp_path / "Kvasir-agent") in json.dumps(payload, ensure_ascii=False)


def test_project_local_quest_memory_artifact_lifecycle(tmp_path: Path):
    new_payload = run_kactl(
        "call",
        "ka_new_quest",
        "--json",
        json.dumps({
            "goal": "Codex native adapter smoke quest",
            "quest_id": "codex-smoke",
            "title": "Codex native adapter smoke quest",
            "workspace_mode": "copilot",
        }),
        "--format",
        "json",
        project_root=tmp_path,
    )
    assert new_payload["ok"] is True
    assert new_payload["quest_id"] == "codex-smoke"

    memory_payload = run_kactl(
        "call",
        "ka_memory_write",
        "--json",
        json.dumps({
            "quest_id": "codex-smoke",
            "title": "Codex adapter smoke memory",
            "kind": "constraint",
            "content": "Codex adapter writes project-local memory without MCP.",
            "scope": "quest",
        }),
        "--format",
        "json",
        project_root=tmp_path,
    )
    assert memory_payload["ok"] is True
    assert memory_payload["kind"] == "knowledge"
    assert "constraint" in memory_payload.get("tags", [])

    artifact_payload = run_kactl(
        "call",
        "ka_artifact_record",
        "--json",
        json.dumps({
            "quest_id": "codex-smoke",
            "kind": "milestone",
            "summary": "Codex native adapter smoke artifact",
            "payload": {"verdict": "pass", "transport": "codex-native-cli"},
        }),
        "--format",
        "json",
        project_root=tmp_path,
    )
    assert artifact_payload["ok"] is True

    state_root = tmp_path / "Kvasir-agent"
    assert (state_root / "research.yaml").exists()
    assert (state_root / "memory" / "knowledge").exists()
    assert (state_root / "artifacts" / "milestones").exists()
    assert not (state_root / "quests" / "codex-smoke").exists()
    assert not (tmp_path / ".mcp.json").exists()


def test_assets_and_docs_are_codex_native_not_hermes_or_mcp_only():
    required = [
        PLUGIN_ROOT / "README.md",
        PLUGIN_ROOT / "docs" / "USAGE.md",
        PLUGIN_ROOT / "docs" / "INSTALL.md",
        PLUGIN_ROOT / "skills" / "kvasir-agent" / "SKILL.md",
        PLUGIN_ROOT / "scripts" / "kactl.py",
        PLUGIN_ROOT / "scripts" / "doctor.py",
        PLUGIN_ROOT / "scripts" / "install.sh",
    ]
    for path in required:
        assert path.exists(), path
    assert (PLUGIN_ROOT / ".mcp.json").exists()
    readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    usage = (PLUGIN_ROOT / "docs" / "USAGE.md").read_text(encoding="utf-8")
    combined = readme + "\n" + usage
    assert "Codex CLI" in combined
    assert "MCP-only default" in combined
    assert "scripts/ka_mcp.py" in combined
    assert "ADMIN_CLI.md" in combined
    assert "CLI fallback" not in combined
    assert "scripts/kactl.py" not in combined


def test_bilingual_readmes_document_current_install_flow():
    readme = (PLUGIN_ROOT / "README.md").read_text()
    chinese = (PLUGIN_ROOT / "README.zh-CN.md").read_text()
    assert "README.zh-CN.md" in readme and "README.md" in chinese
    for text in (readme, chinese):
        assert "scripts/install.sh kvasir-agent@local-personal" in text
        assert "codex plugin list" in text
        assert ".mcp.json" in text
        assert "ka_research_read" in text
        assert "24" in text
    install = (PLUGIN_ROOT / "docs/INSTALL.md").read_text()
    assert "marketplace.json" in install
    assert "codex mcp remove kvasir-agent" in install
    assert "new thread" in install


def test_codex_docs_define_operation_vs_semantic_boundary():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    operator_skill = (PLUGIN_ROOT / "skills" / "kvasir-agent" / "SKILL.md").read_text(encoding="utf-8")
    usage = (PLUGIN_ROOT / "docs" / "USAGE.md").read_text(encoding="utf-8")
    combined = json.dumps(manifest, ensure_ascii=False) + "\n" + operator_skill + "\n" + usage
    required = ["Codex", "ordinary", "ka_bash_exec", "provenance", "baseline"]
    for phrase in required:
        assert phrase in combined


def test_codex_stage_skills_do_not_force_routine_operations_through_ka_bash_exec():
    scanned_roots = [
        PLUGIN_ROOT / "skills",
        PLUGIN_ROOT / "kvasir_agent" / "runtime" / "resources" / "skills",
        PLUGIN_ROOT / "kvasir_agent" / "runtime" / "resources" / "repo" / "src" / "skills",
    ]
    forbidden = [
        "Hard execution rule: every terminal command in this stage must go through `ka_bash_exec`",
        "do not use any other terminal path for smoke tests, real runs, Git, Python, package-manager, or file-inspection commands",
        "do not use any other terminal path for LaTeX builds, figure generation, scripted export, Git, Python, package-manager, or file-inspection commands",
        "do not use any other terminal path for slice execution, smoke tests, Git, Python, package-manager, or file-inspection commands",
        "**Do not use native `shell_command` / `command_execution` in this skill.**",
        "**All shell, CLI, Python, bash, node, git, npm, uv, and environment work must go through `ka_bash_exec ...)`.**",
        "**Any shell, CLI, Python, bash, node, git, npm, uv, or repo-inspection execution must go through `ka_bash_exec ...)`.**",
        "**Any shell, CLI, Python, bash, node, git, npm, uv, or repo-audit execution must go through `ka_bash_exec ...)`.**",
    ]
    offenders: list[str] = []
    for root in scanned_roots:
        for path in root.rglob("SKILL.md"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in forbidden:
                if needle in text:
                    offenders.append(f"{path.relative_to(PLUGIN_ROOT)} contains stale all-terminal rule: {needle}")
    assert not offenders


def test_codex_plugin_packages_distinct_native_workflows_and_retains_references():
    skills = {p.parent.name for p in (PLUGIN_ROOT / "skills").rglob("SKILL.md")}
    assert skills == {"kvasir-agent", "kvasir-agent-experiment", "kvasir-agent-write",
                      "kvasir-agent-strict-research", "kvasir-agent-paper-reliability-verifier",
                      "kvasir-agent-figure-polish", "kvasir-agent-quest-handoffs"}
    for name in ("experiment-execution", "writing-plans", "review", "baseline", "analysis-campaign"):
        archive = PLUGIN_ROOT / "docs/research-playbooks" / f"kvasir-agent-{name}" / "references/legacy-playbook.md"
        assert archive.is_file()
    import re
    for path in (PLUGIN_ROOT / "skills").rglob("SKILL.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" not in target and not target.startswith("#"):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)


def test_installer_delegates_to_codex_and_manifest_bundles_mcp():
    installer = (PLUGIN_ROOT / "scripts/install.sh").read_text()
    assert 'codex plugin add "$1"' in installer
    assert "config.toml" not in installer
    config = json.loads((PLUGIN_ROOT / ".mcp.json").read_text())
    server = config["mcpServers"]["kvasir-agent"]
    assert server["command"] == "python3"
    assert server["args"] == ["scripts/ka_mcp.py"]
    assert server["cwd"] == "."
    assert server["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


def test_no_mcp_transport_or_old_tool_instructions_in_runtime_contexts():
    scanned_roots = [
        PLUGIN_ROOT / "skills",
        PLUGIN_ROOT / "kvasir_agent" / "runtime" / "resources",
        PLUGIN_ROOT / "kvasir_agent" / "runtime" / "vendor" / "kvasiragent" / "runners",
        PLUGIN_ROOT / "kvasir_agent" / "runtime" / "vendor" / "kvasiragent" / "bash_exec",
        PLUGIN_ROOT / "kvasir_agent" / "runtime" / "vendor" / "kvasiragent" / "config",
        PLUGIN_ROOT / "kvasir_agent" / "runtime" / "vendor" / "kvasiragent" / "acp",
    ]
    forbidden = [
        "mcp_servers",
        "transport = \"stdio\"",
        "kvasiragent.mcp.server",
        "_inject_built_in_mcp",
        "Required MCP-driven workflow",
        "artifact.record(",
        "memory.search",
        "memory.write",
        "bash_exec(",
    ]
    offenders: list[str] = []
    for root in scanned_roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".txt", ".yaml", ".yml", ".toml"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in forbidden:
                if needle in text:
                    offenders.append(f"{path.relative_to(PLUGIN_ROOT)} contains {needle}")
    assert not offenders


def test_mcp_equivalent_convenience_tools_are_codex_native():
    payload = run_kactl("list-tools", "--format", "json")
    names = {item["name"] for item in payload["tools"]}
    expected = {
        "ka_memory_list_recent",
        "ka_resolve_runtime_refs",
        "ka_get_paper_contract_health",
        "ka_get_global_status",
        "ka_get_method_scoreboard",
        "ka_get_optimization_frontier",
        "ka_get_conversation_context",
        "ka_list_paper_outlines",
        "ka_refresh_summary",
        "ka_arxiv",
    }
    assert expected <= names
    assert payload["transport"] == "codex-native-cli"
    assert payload["mcp"] is False



def test_mcp_equivalent_convenience_tools_work_without_mcp(tmp_path: Path):
    run_kactl(
        "call",
        "ka_new_quest",
        "--json",
        json.dumps({
            "goal": "Codex native MCP-equivalent convenience coverage smoke quest",
            "quest_id": "codex-mcp-equivalent",
            "title": "Codex native MCP-equivalent convenience coverage smoke quest",
        }),
        "--format",
        "json",
        project_root=tmp_path,
    )
    run_kactl(
        "call",
        "ka_memory_write",
        "--json",
        json.dumps({
            "quest_id": "codex-mcp-equivalent",
            "title": "Recent card for list_recent coverage",
            "kind": "observation",
            "content": "list_recent should expose this quest-local card without MCP.",
            "scope": "quest",
        }),
        "--format",
        "json",
        project_root=tmp_path,
    )
    run_kactl(
        "call",
        "ka_record_user_requirement",
        "--json",
        json.dumps({
            "quest_id": "codex-mcp-equivalent",
            "message": "Remember this conversation item for context coverage.",
        }),
        "--format",
        "json",
        project_root=tmp_path,
    )

    def call(tool: str, args: dict) -> dict:
        return run_kactl("call", tool, "--json", json.dumps(args), "--format", "json", project_root=tmp_path)

    recent = call("ka_memory_list_recent", {"quest_id": "codex-mcp-equivalent", "scope": "quest", "limit": 5})
    assert recent["ok"] is True
    assert recent["count"] >= 1
    assert any(item.get("title") == "Recent card for list_recent coverage" for item in recent["items"])

    refs = call("ka_resolve_runtime_refs", {"quest_id": "codex-mcp-equivalent"})
    assert refs["ok"] is True
    assert "active_idea_id" in refs
    assert "current_canonical_branch" in refs

    paper_health_proc = subprocess.run(
        [
            PYTHON,
            str(PLUGIN_ROOT / "scripts" / "kactl.py"),
            "call",
            "ka_get_paper_contract_health",
            "--json",
            json.dumps({"quest_id": "codex-mcp-equivalent", "detail": "summary"}),
            "--format",
            "json",
        ],
        cwd=str(tmp_path),
        env={**os.environ.copy(), "KVASIR_AGENT_PROJECT_ROOT": str(tmp_path)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert paper_health_proc.returncode in {0, 1}
    paper_health = json.loads(paper_health_proc.stdout)
    assert "ok" in paper_health
    assert paper_health.get("mcp") is False
    assert "paper_contract_health" in paper_health or "message" in paper_health

    global_status = call("ka_get_global_status", {"quest_id": "codex-mcp-equivalent", "detail": "brief", "locale": "zh"})
    assert global_status["ok"] is True
    assert global_status["global_status"]["quest_id"] == "codex-mcp-equivalent"

    scoreboard = call("ka_get_method_scoreboard", {"quest_id": "codex-mcp-equivalent"})
    assert scoreboard["ok"] is True
    assert not Path(scoreboard["scoreboard_path"]).exists()
    assert "scoreboard" in scoreboard

    frontier = call("ka_get_optimization_frontier", {"quest_id": "codex-mcp-equivalent"})
    assert frontier["ok"] is True
    assert "optimization_frontier" in frontier

    context = call("ka_get_conversation_context", {"quest_id": "codex-mcp-equivalent", "limit": 5})
    assert context["ok"] is True
    assert context["count"] >= 1
    assert context["latest_user_message"] is not None

    outlines = call("ka_list_paper_outlines", {"quest_id": "codex-mcp-equivalent"})
    assert outlines["ok"] is True
    assert "outlines" in outlines

    arxiv_list = call("ka_arxiv", {"quest_id": "codex-mcp-equivalent", "mode": "list"})
    assert arxiv_list["ok"] is True
    assert arxiv_list["mode"] == "list"


    assert not (tmp_path / ".mcp.json").exists()



def test_no_mcp_package_or_server_surface_is_bundled():
    vendor = PLUGIN_ROOT / "kvasir_agent" / "runtime" / "vendor" / "kvasiragent"
    assert not (vendor / "mcp").exists()
    assert not any("mcp" in str(path).lower() and path.name == "server.py" for path in vendor.rglob("*.py"))
