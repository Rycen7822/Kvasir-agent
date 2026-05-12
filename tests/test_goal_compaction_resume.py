from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def test_goal_state_survives_context_compaction_via_resume_and_context_pack(tmp_path: Path):
    quest_id = "QRESUME"
    call_tool(
        "cs_manifest_init",
        {"project": str(tmp_path), "name": "demo", "goal": "resume goal", "overwrite": True},
    )
    state = call_tool(
        "cs_goal_state",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "active_stage": "analysis-campaign",
            "current_gate": {"stage": "analysis-campaign", "required_tool": "cs_record_analysis_slice"},
            "next_action": {"action_type": "record_analysis", "required_tool": "cs_record_analysis_slice"},
        },
    )
    assert state["ok"] is True
    state_path = Path(state["path"])
    assert state_path.exists()

    resume = call_tool("cs_resume_brief", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 4000})
    assert resume["ok"] is True
    assert resume["goal_loop_state"]["quest_id"] == quest_id
    assert resume["goal_loop_state"]["active_stage"] == "analysis-campaign"
    assert resume["goal_loop_state"]["current_gate"]["required_tool"] == "cs_record_analysis_slice"

    pack = call_tool("cs_context_pack", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 4000})
    assert pack["ok"] is True
    assert "goal_loop_state" in pack["content"]
    assert "analysis-campaign" in pack["content"]
    assert "cs_record_analysis_slice" in pack["content"]
    assert "scripts/csctl.py" not in json.dumps({"resume": resume, "pack": pack}, ensure_ascii=False)
    assert "CLI fallback" not in json.dumps({"resume": resume, "pack": pack}, ensure_ascii=False)
