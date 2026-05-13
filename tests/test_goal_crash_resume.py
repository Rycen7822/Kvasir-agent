from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def test_goal_watchdog_reports_stuck_runner_without_writing_goal_gate(tmp_path: Path):
    quest = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "crash resume", "title": "Crash Resume"}))
    quest_id = quest["quest"]["quest_id"]

    started = _ok(
        call_tool(
            "cs_runner_start",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "job_id": "job-crash",
                "command": "python train.py",
                "dry_run": False,
            },
        )
    )
    run_id = started["run"]["run_id"]
    watchdog = _ok(call_tool("cs_goal_watchdog", {"project": str(tmp_path), "quest_id": quest_id, "timeout_seconds": 0}))
    assert watchdog["stuck_runs"] == [run_id]
    assert watchdog["diagnostic"]["runner_stuck"] is True
    assert set(watchdog["diagnostic"]["recommended_evidence"]) == {"cs_log_digest", "cs_runner_status", "cs_queue_reconcile"}
    assert "current_gate" not in watchdog

    goal_state_path = tmp_path / "CodexScientist" / "quests" / quest_id / "runtime" / "goal_state.json"
    assert not goal_state_path.exists()

    resume = _ok(call_tool("cs_resume_brief", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 4000}))
    assert resume["active_run_id"] == run_id
    assert resume["blocker"] != "runner_stuck"
    assert "next_required_mcp_tool" not in resume
    assert any(ref["kind"] == "legacy_goal_state_ignored" for ref in resume["source_refs"])
