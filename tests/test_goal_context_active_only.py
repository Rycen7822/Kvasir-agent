from __future__ import annotations

import json

from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload


def _assert_no_cli_text(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    assert "scripts/csctl.py" not in text
    assert "CLI fallback" not in text


def test_goal_context_and_next_action_are_not_default_agent_surface():
    for payload in (tools_list_payload(), tools_list_payload({"profile": "goal"}), tools_list_payload({"profile": "evidence"})):
        assert payload["ok"] is True
        names = {tool["name"] for tool in payload["tools"]}
        assert "cs_goal_context" not in names
        assert "cs_goal_next_action" not in names
        assert "cs_goal_state" not in names
        _assert_no_cli_text(payload)


def test_legacy_goal_context_keeps_no_cli_text_when_called_directly(tmp_path):
    quest_id = "QCTX"
    state = call_tool(
        "cs_goal_state",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "active_stage": "experiment",
            "current_gate": {"stage": "experiment", "action_type": "run_experiment", "required_tool": "cs_record_main_experiment"},
            "completion_criteria": ["toy evidence recorded"],
        },
    )
    assert state["ok"] is True

    context = call_tool("cs_goal_context", {"project": str(tmp_path), "quest_id": quest_id, "user_goal": "继续"})
    assert context["ok"] is True
    assert context["quest_id"] == quest_id
    _assert_no_cli_text(context)
