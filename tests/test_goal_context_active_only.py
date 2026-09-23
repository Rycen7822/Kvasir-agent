from __future__ import annotations

import json

from kvasir_agent.mcp.tool_registry import call_tool, tools_list_payload


def _assert_no_cli_text(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    assert "scripts/kactl.py" not in text
    assert "CLI fallback" not in text


def test_goal_context_and_next_action_are_not_default_agent_surface():
    for payload in (tools_list_payload(), tools_list_payload({"profile": "goal"}), tools_list_payload({"profile": "evidence"})):
        assert payload["ok"] is True
        names = {tool["name"] for tool in payload["tools"]}
        assert "ka_goal_context" not in names
        assert "ka_goal_next_action" not in names
        assert "ka_goal_state" not in names
        _assert_no_cli_text(payload)
