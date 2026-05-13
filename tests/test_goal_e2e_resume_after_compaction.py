from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool
from test_goal_e2e_toy_research import FORBIDDEN, run_toy_goal_research


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def test_goal_e2e_resume_after_compaction_preserves_passive_recovery_anchors(tmp_path: Path):
    result = run_toy_goal_research(tmp_path)
    quest_id = result["quest_id"]

    resume = _ok(call_tool("cs_resume_brief", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 1600}))
    pack = _ok(call_tool("cs_context_pack", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 1600}))

    assert resume["current_quest"] == quest_id
    assert resume["last_completed_action"] == "claim-gate"
    assert resume["recovery_anchor"] == "continue with a real experiment or stop toy validation"
    assert "goal_loop_state" not in resume
    assert "next_required_mcp_tool" not in resume
    assert "## quest_state" in pack["content"]
    assert "## recovery_anchor" in pack["content"]
    assert "goal_loop_state" not in pack["content"]
    assert "toy-e2e" in json.dumps(resume, ensure_ascii=False) or "toy-e2e" in pack["content"]

    combined = json.dumps({"resume": resume, "pack": pack}, ensure_ascii=False)
    for forbidden in FORBIDDEN:
        assert forbidden not in combined
