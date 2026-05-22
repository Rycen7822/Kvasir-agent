from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def test_legacy_goal_state_is_ignored_by_resume_and_context_pack(tmp_path: Path):
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
    assert "goal_loop_state" not in resume
    assert "next_required_mcp_tool" not in resume
    assert any(ref["kind"] == "goal_state" for ref in resume["source_refs"])
    assert not any(ref["kind"] == "legacy_goal_state_ignored" for ref in resume["source_refs"])

    pack = call_tool("cs_context_pack", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 4000})
    assert pack["ok"] is True
    assert "## quest_state" in pack["content"]
    assert "## recovery_anchor" in pack["content"]
    assert "goal_loop_state" not in pack["content"]
    assert "cs_record_analysis_slice" not in pack["content"]
    assert "scripts/csctl.py" not in json.dumps({"resume": resume, "pack": pack}, ensure_ascii=False)
    assert "CLI fallback" not in json.dumps({"resume": resume, "pack": pack}, ensure_ascii=False)
