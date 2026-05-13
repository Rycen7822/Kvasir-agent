from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def test_state_changing_tools_do_not_report_or_write_progress_watchdog(tmp_path: Path):
    quest = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "watchdog", "title": "Watchdog"}))
    quest_id = quest["quest"]["quest_id"]

    first = _ok(
        call_tool(
            "cs_record_user_requirement",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "message": "require bounded progress checkpoints",
                "stage": "scout",
                "checkpoint_tool_threshold": 2,
            },
        )
    )
    second = _ok(
        call_tool(
            "cs_record_user_requirement",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "message": "second state change",
                "stage": "scout",
                "checkpoint_tool_threshold": 2,
            },
        )
    )

    for payload in (first, second):
        assert "checkpoint_due" not in payload
        assert "checkpoint_reason" not in payload
        assert "next_checkpoint_tool" not in payload
        assert "progress_watchdog" not in payload

    state_path = tmp_path / "CodexScientist" / "quests" / quest_id / "runtime" / "progress_watchdog.json"
    assert not state_path.exists()


def test_checkpoint_writes_passive_checkpoint_without_watchdog_or_goal_gate(tmp_path: Path):
    quest = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "watchdog reset", "title": "Watchdog Reset"}))
    quest_id = quest["quest"]["quest_id"]
    _ok(
        call_tool(
            "cs_record_user_requirement",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "message": "state change",
                "checkpoint_tool_threshold": 1,
            },
        )
    )

    checkpoint = _ok(
        call_tool(
            "cs_checkpoint",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "phase": "watchdog",
                "completed": ["state change"],
                "next_action": "continue",
            },
        )
    )
    assert checkpoint["checkpoint_id"]
    assert Path(checkpoint["latest_path"]).exists()
    assert Path(checkpoint["checkpoint_log_path"]).exists()
    assert "checkpoint_due" not in checkpoint
    assert "next_checkpoint_tool" not in checkpoint
    assert "runtime_checkpoint_path" not in checkpoint
    assert "goal_state_path" not in checkpoint
    assert "progress_watchdog" not in checkpoint

    quest_runtime = tmp_path / "CodexScientist" / "quests" / quest_id / "runtime"
    assert not (quest_runtime / "progress_watchdog.json").exists()
    goal_state = quest_runtime / "goal_state.json"
    assert not goal_state.exists()
