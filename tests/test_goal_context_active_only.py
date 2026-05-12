from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _assert_no_cli_text(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    assert "scripts/csctl.py" not in text
    assert "CLI fallback" not in text


def test_goal_context_returns_active_stage_only_and_one_companion(tmp_path: Path):
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
    assert context["active_stage"] == "experiment"
    assert context["context"]["active_stage"] == "experiment"
    assert context["current_gate"]["required_tool"] == "cs_record_main_experiment"
    assert len(context["stage_skills"]) == 1
    assert len(context["companion_skills"]) <= 1
    assert context["stage_skills"][0]["skill_id"] == "experiment"
    assert "cs_record_main_experiment" in context["allowed_tools_for_stage"]
    assert "cs_submit_paper_bundle" not in context["allowed_tools_for_stage"]
    assert context["no_cli_text_guarantee"] is True
    _assert_no_cli_text(context)


def test_goal_next_action_is_machine_readable_and_stage_bounded(tmp_path: Path):
    quest_id = "QNEXT"
    call_tool(
        "cs_goal_state",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "active_stage": "baseline",
            "current_gate": {"stage": "baseline", "blocking_reason": "baseline_missing"},
        },
    )

    action = call_tool("cs_goal_next_action", {"project": str(tmp_path), "quest_id": quest_id, "user_goal": "continue"})
    assert action["ok"] is True
    assert action["quest_id"] == quest_id
    assert action["active_stage"] == "baseline"
    assert action["next_action"]["action_type"] == "establish_baseline"
    assert action["next_action"]["required_tool"] == "cs_create_local_baseline"
    assert action["next_action"]["done_when"]
    _assert_no_cli_text(action)
