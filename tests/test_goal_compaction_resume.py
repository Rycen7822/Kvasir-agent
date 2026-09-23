from __future__ import annotations

import json
from pathlib import Path

from kvasir_agent.mcp.tool_registry import call_tool


def test_legacy_goal_state_is_ignored_by_resume_and_context_pack(tmp_path: Path):
    quest_id = "QRESUME"
    call_tool(
        "ka_manifest_init",
        {"project": str(tmp_path), "name": "demo", "goal": "resume goal", "overwrite": True},
    )
    state_path = tmp_path / "Kvasir-agent/runtime/goal_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_state = {"next_action": {"required_tool": "ka_record_analysis_slice"}}
    state_path.write_text(json.dumps(legacy_state))

    resume = call_tool("ka_resume_brief", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 4000})
    assert resume["ok"] is True
    assert "goal_loop_state" not in resume
    assert "next_required_mcp_tool" not in resume
    assert not any(ref["kind"] == "goal_state" for ref in resume["source_refs"])
    assert json.loads(state_path.read_text()) == legacy_state
    assert not any(ref["kind"] == "legacy_goal_state_ignored" for ref in resume["source_refs"])

    pack = call_tool("ka_context_pack", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 4000})
    assert pack["ok"] is True
    assert "## quest_state" in pack["content"]
    assert "## recovery_anchor" in pack["content"]
    assert "goal_loop_state" not in pack["content"]
    assert "ka_record_analysis_slice" not in pack["content"]
    assert "scripts/kactl.py" not in json.dumps({"resume": resume, "pack": pack}, ensure_ascii=False)
    assert "CLI fallback" not in json.dumps({"resume": resume, "pack": pack}, ensure_ascii=False)
