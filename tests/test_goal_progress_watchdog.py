from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def test_state_changing_tools_report_checkpoint_due_and_watchdog_state(tmp_path: Path):
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
    assert first["checkpoint_due"] is False

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
    assert second["checkpoint_due"] is True
    assert second["checkpoint_reason"] == "tool_call_threshold"
    assert second["next_checkpoint_tool"] == "cs_checkpoint"

    state_path = tmp_path / "CodexScientist" / "quests" / quest_id / "runtime" / "progress_watchdog.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["tool_calls_since_last_checkpoint"] == 2
    assert state["last_state_changing_tool"] == "cs_record_user_requirement"
    assert state["pending_checkpoint_reason"] == "tool_call_threshold"


def test_checkpoint_resets_progress_watchdog_and_writes_runtime_checkpoint(tmp_path: Path):
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
    assert checkpoint["checkpoint_due"] is False
    assert checkpoint["runtime_checkpoint_path"].endswith(".md")
    assert Path(checkpoint["runtime_checkpoint_path"]).exists()
    assert Path(checkpoint["runtime_summary_path"]).exists()
    assert Path(checkpoint["goal_state_path"]).exists()

    state = json.loads((tmp_path / "CodexScientist" / "quests" / quest_id / "runtime" / "progress_watchdog.json").read_text(encoding="utf-8"))
    assert state["tool_calls_since_last_checkpoint"] == 0
    assert state["pending_checkpoint_reason"] is None
