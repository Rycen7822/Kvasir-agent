from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

FORBIDDEN_DEFAULT_PHRASES = (
    "CLI fallback",
    "scripts/csctl.py",
)

P4_TARGETED_TESTS = (
    "tests/test_no_cli_prompt_surface.py",
    "tests/test_hidden_admin_cli_compat.py",
    "tests/test_mcp_goal_tool_surface.py",
    "tests/test_mcp_goal_research_loop.py",
    "tests/test_goal_quest_layout.py",
    "tests/test_goal_layout_migrates_legacy_state.py",
    "tests/test_goal_context_active_only.py",
    "tests/test_goal_stage_router.py",
    "tests/test_goal_compaction_resume.py",
    "tests/test_method_improvement_loop.py",
    "tests/test_claim_evidence_gate.py",
    "tests/test_goal_progress_watchdog.py",
    "tests/test_goal_crash_resume.py",
    "tests/test_goal_long_run_soak.py",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="replace")


def test_p4_acceptance_script_exists_and_declares_required_gates():
    script = ROOT / "scripts" / "p4_acceptance.py"
    assert script.exists(), "P4 must have one stable local/CI acceptance entrypoint"
    source = script.read_text(encoding="utf-8")
    ast.parse(source)

    for phrase in [
        "compileall",
        "pytest",
        "cs_mcp.py",
        "tools/list",
        "initialize",
        "find_agent_facing_cli_violations",
        "test_goal_long_run_soak.py",
        "test_goal_crash_resume.py",
    ]:
        assert phrase in source
    for test_path in P4_TARGETED_TESTS:
        assert test_path in source


def test_p4_acceptance_script_runs_fast_suite_successfully():
    proc = subprocess.run(
        [PYTHON, "scripts/p4_acceptance.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    output = proc.stdout + proc.stderr
    assert "P4 acceptance passed" in output
    assert "violations 0" in output


def test_ci_runs_p4_acceptance_and_mcp_smokes():
    ci = _read(".github/workflows/ci.yml")
    assert "python scripts/p4_acceptance.py" in ci
    assert "python -m pytest -q" in ci
    assert "python -m vulture codex_scientist scripts tests --min-confidence 100" in ci
    assert "python scripts/cs_mcp.py --stdio-smoke tools/list" in ci
    assert "python scripts/cs_mcp.py --stdio-smoke initialize" in ci


def test_default_docs_are_mcp_only_and_admin_cli_is_isolated():
    default_docs = "\n".join(
        _read(path)
        for path in (
            "README.md",
            "README.zh-CN.md",
            "docs/ARCHITECTURE.md",
            "docs/REPOSITORY_LAYOUT.md",
            "docs/USAGE.md",
            "docs/MCP.md",
            "docs/LONG_RUN.md",
            "docs/P4_TERMS.md",
        )
    )
    assert "MCP-only default" in default_docs
    assert "`/goal` is Codex-native" in default_docs
    assert "cs_goal_watchdog" in default_docs
    assert "progress watchdog" in default_docs
    assert "claim gate" in default_docs
    for forbidden in FORBIDDEN_DEFAULT_PHRASES:
        assert forbidden not in default_docs

    admin = _read("docs/ADMIN_CLI.md")
    assert "hidden admin/debug CLI" in admin
    assert "scripts/csctl.py" in admin
    assert "human/admin/debug/CI/recovery" in admin


def test_mcp_doc_lists_current_profiles_and_goal_tools():
    text = _read("docs/MCP.md")
    for phrase in [
        "core profile: 14 tools",
        "goal profile: 47 tools",
        "active stage subset",
        "cs_goal_context",
        "cs_goal_watchdog",
        "cs_update_method_scoreboard",
        "cs_select_next_idea",
        "cs_claim_gate",
        "cs_trial_show",
        "fail closed",
    ]:
        assert phrase in text
    assert "default curated surface currently has 20 tools" not in text


def test_long_run_doc_spells_out_watchdog_checkpoint_resume_contract():
    text = _read("docs/LONG_RUN.md")
    for phrase in [
        "progress watchdog",
        "checkpoint_due",
        "cs_goal_watchdog",
        "cs_checkpoint",
        "cs_resume_brief",
        "runner_stuck",
        "next_required_mcp_tool",
        "active_run_id",
        "wall-clock: not_run",
    ]:
        assert phrase in text
