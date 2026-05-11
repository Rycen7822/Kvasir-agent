from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parent
PYTHON = sys.executable


def run_dsctl(*args: str, project_root: Path | None = None) -> dict:
    env = os.environ.copy()
    if project_root is not None:
        env["DEEPSCIENTIST_PROJECT_ROOT"] = str(project_root)
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "dsctl.py"), *args],
        cwd=str(project_root or PLUGIN_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_codex_manifest_is_native_and_not_mcp():
    manifest_path = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["name"] == "deepscientist-codex"
    assert manifest["skills"] == "./skills"
    assert "mcpServers" not in manifest
    assert "mcp" not in json.dumps(manifest, ensure_ascii=False).lower()


def test_dsctl_exposes_complete_native_schema_set():
    sys.path.insert(0, str(PLUGIN_ROOT))
    from deepscientist_native import schemas

    payload = run_dsctl("list-tools", "--format", "json")
    names = {item["name"] for item in payload["tools"]}
    expected = {schema["name"] for schema in schemas.NATIVE_SCHEMAS}
    assert payload["ok"] is True
    assert expected <= names
    assert payload["transport"] == "codex-native-cli"
    assert payload["mcp"] is False


def test_dsctl_public_tools_are_canonical_ds_surface():
    payload = run_dsctl("list-tools", "--format", "json")
    names = {item["name"] for item in payload["tools"]}
    assert payload["ok"] is True
    assert payload["transport"] == "codex-native-cli"
    assert payload["mcp"] is False
    assert "ds_events" in names
    assert not any(name.startswith("deepscientist_") for name in names)
    assert payload["count"] == 48

    schema_payload = run_dsctl("schema", "--format", "json")
    schema_names = {schema["name"] for schema in schema_payload["schemas"]}
    assert "ds_events" in schema_names
    assert not any(name.startswith("deepscientist_") for name in schema_names)


def test_legacy_deepscientist_aliases_are_hidden_but_call_compatible(tmp_path: Path):
    run_dsctl(
        "call",
        "ds_new_quest",
        "--json",
        json.dumps({
            "goal": "Legacy alias compatibility smoke quest",
            "quest_id": "alias-smoke",
            "title": "Legacy alias compatibility smoke quest",
            "workspace_mode": "copilot",
        }),
        "--format",
        "json",
        project_root=tmp_path,
    )
    payload = run_dsctl(
        "call",
        "deepscientist_status",
        "--json",
        json.dumps({"quest_id": "alias-smoke"}),
        "--format",
        "json",
        project_root=tmp_path,
    )
    assert payload["ok"] is True
    assert payload["deprecated_alias"] is True
    assert payload["legacy_tool"] == "deepscientist_status"
    assert payload["canonical_tool"] == "ds_get_quest_state"


def test_dsctl_doctor_uses_vendored_runtime_without_external_ds(tmp_path: Path):
    payload = run_dsctl("doctor", "--format", "json", project_root=tmp_path)
    assert payload["ok"] is True
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["vendored_runtime_import"]["ok"] is True
    assert checks["no_external_ds_required"]["ok"] is True
    assert str(tmp_path / "DeepScientist") in json.dumps(payload, ensure_ascii=False)


def test_project_local_quest_memory_artifact_lifecycle(tmp_path: Path):
    new_payload = run_dsctl(
        "call",
        "ds_new_quest",
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

    memory_payload = run_dsctl(
        "call",
        "ds_memory_write",
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

    artifact_payload = run_dsctl(
        "call",
        "ds_artifact_record",
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

    assert (tmp_path / "DeepScientist" / "quests" / "codex-smoke").exists()
    assert not (tmp_path / ".mcp.json").exists()


def test_assets_and_docs_are_codex_native_not_hermes_or_mcp_only():
    required = [
        PLUGIN_ROOT / "README.md",
        PLUGIN_ROOT / "docs" / "USAGE.md",
        PLUGIN_ROOT / "docs" / "INSTALL.md",
        PLUGIN_ROOT / "skills" / "deepscientist-codex" / "SKILL.md",
        PLUGIN_ROOT / "scripts" / "dsctl.py",
        PLUGIN_ROOT / "scripts" / "doctor.py",
        PLUGIN_ROOT / "scripts" / "install.sh",
    ]
    for path in required:
        assert path.exists(), path
    assert not (PLUGIN_ROOT / ".mcp.json").exists()
    readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    usage = (PLUGIN_ROOT / "docs" / "USAGE.md").read_text(encoding="utf-8")
    combined = readme + "\n" + usage
    assert "Codex CLI" in combined
    assert "not MCP" in combined or "no MCP" in combined
    assert "external ds" in combined
    assert "scripts/dsctl.py" in combined


def test_bilingual_readmes_document_current_install_flow():
    readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    zh_readme = (PLUGIN_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    install_doc = (PLUGIN_ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    combined_install = readme + "\n" + zh_readme + "\n" + install_doc

    assert "README.zh-CN.md" in readme
    assert "README.md" in zh_readme
    for phrase in [
        "48-tool public canonical `ds_*`",
        "48 个 canonical `ds_*`",
        "legacy `deepscientist_*`",
        "历史 `deepscientist_*`",
        "ds_events",
        "scripts/install.sh",
        "scripts/init_project.sh",
        "marketplace.json",
        "config.toml",
        "CODEX_HOME",
        "AGENTS_HOME",
        "backup",
    ]:
        assert phrase in combined_install


def test_codex_docs_define_operation_vs_semantic_boundary():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    operator_skill = (PLUGIN_ROOT / "skills" / "deepscientist-codex" / "SKILL.md").read_text(encoding="utf-8")
    usage = (PLUGIN_ROOT / "docs" / "USAGE.md").read_text(encoding="utf-8")
    combined = json.dumps(manifest, ensure_ascii=False) + "\n" + operator_skill + "\n" + usage
    required = [
        "Codex-native operation boundary",
        "Codex-native operation layer",
        "DeepScientist semantic/provenance layer",
        "Codex does the mechanical action; DeepScientist records the research meaning",
        "ds_bash_exec` only when the command itself must be auditable DeepScientist provenance",
        "not as a general shell replacement",
        "routine file, shell, Git, test, build, and process work",
    ]
    for phrase in required:
        assert phrase in combined


def test_codex_stage_skills_do_not_force_routine_operations_through_ds_bash_exec():
    scanned_roots = [
        PLUGIN_ROOT / "skills",
        PLUGIN_ROOT / "deepscientist_native" / "resources" / "skills",
        PLUGIN_ROOT / "deepscientist_native" / "resources" / "repo" / "src" / "skills",
    ]
    forbidden = [
        "Hard execution rule: every terminal command in this stage must go through `ds_bash_exec`",
        "do not use any other terminal path for smoke tests, real runs, Git, Python, package-manager, or file-inspection commands",
        "do not use any other terminal path for LaTeX builds, figure generation, scripted export, Git, Python, package-manager, or file-inspection commands",
        "do not use any other terminal path for slice execution, smoke tests, Git, Python, package-manager, or file-inspection commands",
        "**Do not use native `shell_command` / `command_execution` in this skill.**",
        "**All shell, CLI, Python, bash, node, git, npm, uv, and environment work must go through `ds_bash_exec ...)`.**",
        "**Any shell, CLI, Python, bash, node, git, npm, uv, or repo-inspection execution must go through `ds_bash_exec ...)`.**",
        "**Any shell, CLI, Python, bash, node, git, npm, uv, or repo-audit execution must go through `ds_bash_exec ...)`.**",
    ]
    offenders: list[str] = []
    for root in scanned_roots:
        for path in root.rglob("SKILL.md"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in forbidden:
                if needle in text:
                    offenders.append(f"{path.relative_to(PLUGIN_ROOT)} contains stale all-terminal rule: {needle}")
    assert not offenders


def test_codex_plugin_packages_deep_integrated_deepscientist_skills():
    expected_skill_ids = {
        "experiment-execution": ["ds_bash_exec", "planned_not_executed", "baseline gate"],
        "quest-handoffs": ["AGENTS.md", "handoff", "ds_artifact_record"],
        "writing-plans": ["Implementation Plan", "ds_bash_exec", "DeepScientist"],
        "paper-reliability-verification": ["ds_paper_reliability_verify", "OpenReview", "accepted_publication"],
        "review": ["paper/review/review.md", "ds_bash_exec", "claim downgrade"],
    }
    for skill_id, phrases in expected_skill_ids.items():
        resource_skill = PLUGIN_ROOT / "deepscientist_native" / "resources" / "skills" / skill_id / "SKILL.md"
        repo_resource_skill = PLUGIN_ROOT / "deepscientist_native" / "resources" / "repo" / "src" / "skills" / skill_id / "SKILL.md"
        codex_skill = PLUGIN_ROOT / "skills" / f"deepscientist-{skill_id}" / "SKILL.md"
        assert resource_skill.exists(), resource_skill
        assert repo_resource_skill.exists(), repo_resource_skill
        assert codex_skill.exists(), codex_skill
        combined = resource_skill.read_text(encoding="utf-8") + "\n" + repo_resource_skill.read_text(encoding="utf-8") + "\n" + codex_skill.read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase in combined, f"deepscientist-{skill_id} missing {phrase}"
        assert "artifact.record(" not in combined
        assert "memory.write" not in combined
        assert "bash_exec(" not in combined
        assert "Hermes compatibility note" not in combined
        assert "Hermes `memory(" not in combined
        assert "Use Hermes tools" not in combined


def test_installer_registers_codex_plugin_without_mcp():
    installer = (PLUGIN_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert "~/.codex/plugins/deepscientist-codex" in installer
    assert "marketplace.json" in installer
    assert '[plugins."deepscientist-codex@local-personal"]' in installer
    assert "mcpServers" not in installer


def test_no_mcp_transport_or_old_tool_instructions_in_runtime_contexts():
    scanned_roots = [
        PLUGIN_ROOT / "skills",
        PLUGIN_ROOT / "deepscientist_native" / "resources",
        PLUGIN_ROOT / "deepscientist_native" / "vendor" / "deepscientist" / "runners",
        PLUGIN_ROOT / "deepscientist_native" / "vendor" / "deepscientist" / "bash_exec",
        PLUGIN_ROOT / "deepscientist_native" / "vendor" / "deepscientist" / "config",
        PLUGIN_ROOT / "deepscientist_native" / "vendor" / "deepscientist" / "acp",
    ]
    forbidden = [
        "mcp_servers",
        "transport = \"stdio\"",
        "deepscientist.mcp.server",
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
    payload = run_dsctl("list-tools", "--format", "json")
    names = {item["name"] for item in payload["tools"]}
    expected = {
        "ds_memory_list_recent",
        "ds_resolve_runtime_refs",
        "ds_get_paper_contract_health",
        "ds_get_global_status",
        "ds_get_method_scoreboard",
        "ds_get_optimization_frontier",
        "ds_get_conversation_context",
        "ds_list_paper_outlines",
        "ds_refresh_summary",
        "ds_arxiv",
    }
    assert expected <= names
    assert payload["transport"] == "codex-native-cli"
    assert payload["mcp"] is False



def test_mcp_equivalent_convenience_tools_work_without_mcp(tmp_path: Path):
    run_dsctl(
        "call",
        "ds_new_quest",
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
    run_dsctl(
        "call",
        "ds_memory_write",
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
    run_dsctl(
        "call",
        "ds_record_user_requirement",
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
        return run_dsctl("call", tool, "--json", json.dumps(args), "--format", "json", project_root=tmp_path)

    recent = call("ds_memory_list_recent", {"quest_id": "codex-mcp-equivalent", "scope": "quest", "limit": 5})
    assert recent["ok"] is True
    assert recent["count"] >= 1
    assert any(item.get("title") == "Recent card for list_recent coverage" for item in recent["items"])

    refs = call("ds_resolve_runtime_refs", {"quest_id": "codex-mcp-equivalent"})
    assert refs["ok"] is True
    assert "active_idea_id" in refs
    assert "current_canonical_branch" in refs

    paper_health_proc = subprocess.run(
        [
            PYTHON,
            str(PLUGIN_ROOT / "scripts" / "dsctl.py"),
            "call",
            "ds_get_paper_contract_health",
            "--json",
            json.dumps({"quest_id": "codex-mcp-equivalent", "detail": "summary"}),
            "--format",
            "json",
        ],
        cwd=str(tmp_path),
        env={**os.environ.copy(), "DEEPSCIENTIST_PROJECT_ROOT": str(tmp_path)},
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

    global_status = call("ds_get_global_status", {"quest_id": "codex-mcp-equivalent", "detail": "brief", "locale": "zh"})
    assert global_status["ok"] is True
    assert global_status["global_status"]["quest_id"] == "codex-mcp-equivalent"

    scoreboard = call("ds_get_method_scoreboard", {"quest_id": "codex-mcp-equivalent"})
    assert scoreboard["ok"] is True
    assert Path(scoreboard["json_path"]).exists()
    assert "scoreboard" in scoreboard

    frontier = call("ds_get_optimization_frontier", {"quest_id": "codex-mcp-equivalent"})
    assert frontier["ok"] is True
    assert "optimization_frontier" in frontier

    context = call("ds_get_conversation_context", {"quest_id": "codex-mcp-equivalent", "limit": 5})
    assert context["ok"] is True
    assert context["count"] >= 1
    assert context["latest_user_message"] is not None

    outlines = call("ds_list_paper_outlines", {"quest_id": "codex-mcp-equivalent"})
    assert outlines["ok"] is True
    assert "outlines" in outlines

    arxiv_list = call("ds_arxiv", {"quest_id": "codex-mcp-equivalent", "mode": "list"})
    assert arxiv_list["ok"] is True
    assert arxiv_list["mode"] == "list"

    summary = call("ds_refresh_summary", {"quest_id": "codex-mcp-equivalent", "reason": "contract test"})
    assert summary["ok"] is True
    assert Path(summary["summary_path"]).exists()

    assert not (tmp_path / ".mcp.json").exists()



def test_no_mcp_package_or_server_surface_is_bundled():
    vendor = PLUGIN_ROOT / "deepscientist_native" / "vendor" / "deepscientist"
    assert not (vendor / "mcp").exists()
    assert not any("mcp" in str(path).lower() and path.name == "server.py" for path in vendor.rglob("*.py"))
