from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def test_crash_resume_links_stuck_runner_to_goal_next_action_and_resume_brief(tmp_path: Path):
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

    action = _ok(call_tool("cs_goal_next_action", {"project": str(tmp_path), "quest_id": quest_id}))
    assert action["next_action"]["required_tool"] in {"cs_log_digest", "cs_runner_status", "cs_queue_reconcile"}
    assert action["next_action"]["blocking_reason"] == "runner_stuck"
    assert action["next_action"]["run_id"] == run_id

    resume = _ok(call_tool("cs_resume_brief", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 4000}))
    assert resume["active_run_id"] == run_id
    assert resume["blocker"] == "runner_stuck"
    assert resume["next_required_mcp_tool"] in {"cs_log_digest", "cs_runner_status", "cs_queue_reconcile"}
    assert any(ref["kind"] == "goal_loop_state" for ref in resume["source_refs"])
