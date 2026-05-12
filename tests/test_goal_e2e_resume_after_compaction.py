from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool
from test_goal_e2e_toy_research import FORBIDDEN, run_toy_goal_research


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def test_goal_e2e_resume_after_compaction_preserves_next_action(tmp_path: Path):
    result = run_toy_goal_research(tmp_path)
    quest_id = result["quest_id"]

    before = _ok(call_tool("cs_goal_next_action", {"project": str(tmp_path), "quest_id": quest_id}))
    resume = _ok(call_tool("cs_resume_brief", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 1600}))
    pack = _ok(call_tool("cs_context_pack", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 1600}))
    after = _ok(call_tool("cs_goal_next_action", {"project": str(tmp_path), "quest_id": quest_id}))

    assert resume["current_quest"] == quest_id
    assert resume["last_completed_action"] == "claim-gate"
    assert resume["goal_loop_state"]["quest_id"] == quest_id
    assert "goal_loop_state" in pack["content"]
    assert "toy-e2e" in json.dumps(resume, ensure_ascii=False) or "toy-e2e" in pack["content"]
    assert before["next_action"] == after["next_action"]
    assert after["next_action"]["required_tool"]

    combined = json.dumps({"resume": resume, "pack": pack, "after": after}, ensure_ascii=False)
    for forbidden in FORBIDDEN:
        assert forbidden not in combined
