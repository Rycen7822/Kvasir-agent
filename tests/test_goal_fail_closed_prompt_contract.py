from __future__ import annotations

import json

from kvasir_agent.mcp.tool_registry import call_tool


def test_goal_tools_fail_closed_without_cli_recommendation(tmp_path):
    missing_context = call_tool("ka_goal_next_action", {"project": str(tmp_path)})
    assert missing_context["ok"] is False
    text = json.dumps(missing_context, ensure_ascii=False)
    assert "quest_id" in text
    assert "scripts/kactl.py" not in text
    assert "CLI fallback" not in text
    assert "recover" in text or "tools/list" in text

    unknown = call_tool("ka_missing_goal_tool", {})
    assert unknown["ok"] is False
    assert unknown["error_type"] == "unknown_tool"
    text = json.dumps(unknown, ensure_ascii=False)
    assert "scripts/kactl.py" not in text
    assert "CLI fallback" not in text
