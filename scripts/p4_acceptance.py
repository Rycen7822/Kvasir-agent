#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

P4_TARGETED_TESTS = [
    "tests/test_no_cli_prompt_surface.py",
    "tests/test_hidden_admin_cli_compat.py",
    "tests/test_mcp_goal_tool_surface.py",
    "tests/test_mcp_goal_research_loop.py",
    "tests/test_goal_runner_queue_trial_manifest_bridge.py",
    "tests/test_goal_profile_no_all_tools_default.py",
    "tests/test_goal_quest_layout.py",
    "tests/test_goal_layout_migrates_legacy_state.py",
    "tests/test_goal_context_active_only.py",
    "tests/test_goal_stage_router.py",
    "tests/test_goal_compaction_resume.py",
    "tests/test_codex_goal_boundary_contract.py",
    "tests/test_goal_fail_closed_prompt_contract.py",
    "tests/test_method_improvement_loop.py",
    "tests/test_novelty_candidate_contract.py",
    "tests/test_novelty_deterministic_scoring.py",
    "tests/test_novelty_duplicate_block.py",
    "tests/test_novelty_related_work_gate.py",
    "tests/test_claim_evidence_gate.py",
    "tests/test_goal_progress_watchdog.py",
    "tests/test_goal_crash_resume.py",
    "tests/test_goal_long_run_soak.py",
    "tests/test_goal_e2e_toy_research.py",
    "tests/test_goal_e2e_no_cli_invocation.py",
    "tests/test_goal_e2e_resume_after_compaction.py",
]


def run(label: str, command: list[str]) -> None:
    print(f"[p4] {label}: {' '.join(command)}", flush=True)
    proc = subprocess.run(command, cwd=ROOT, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def verify_surface_scan() -> None:
    code = """
from pathlib import Path
from codex_scientist.mcp.surface_allowlist import find_agent_facing_cli_violations
root = Path.cwd()
violations = find_agent_facing_cli_violations(root)
print('violations', len(violations))
if violations:
    for item in violations[:20]:
        print(item)
    raise SystemExit(1)
"""
    run("no CLI surface scan", [PYTHON, "-c", code])


def main() -> int:
    run("compileall", [PYTHON, "-m", "compileall", "-q", "codex_scientist", "scripts", "tests"])
    run("targeted pytest", [PYTHON, "-m", "pytest", *P4_TARGETED_TESTS, "-q"])
    run("MCP tools/list smoke", [PYTHON, "scripts/cs_mcp.py", "--stdio-smoke", "tools/list"])
    run("MCP initialize smoke", [PYTHON, "scripts/cs_mcp.py", "--stdio-smoke", "initialize"])
    verify_surface_scan()
    print("P4 acceptance passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
