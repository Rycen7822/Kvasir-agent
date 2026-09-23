from __future__ import annotations

import json

from kvasir_agent.mcp.tool_registry import tools_list_payload


def _names(payload: dict) -> set[str]:
    assert payload.get("ok") is True, payload
    return {tool["name"] for tool in payload.get("tools", [])}


def _warnings_text(payload: dict) -> str:
    return json.dumps(payload.get("warnings", []), ensure_ascii=False, sort_keys=True)


def test_default_core_surface_has_no_planner_or_execution_tools():
    names = _names(tools_list_payload({}))

    forbidden = {
        "ka_goal_context",
        "ka_goal_state",
        "ka_goal_next_action",
        "ka_goal_watchdog",
        "ka_queue_submit",
        "ka_queue_status",
        "ka_runner_start",
        "ka_runner_status",
        "ka_trial_propose",
        "ka_trial_plan",
        "ka_trial_ready",
        "ka_trial_evaluate",
        "ka_trial_decide",
        "ka_select_next_idea",
        "ka_bash_exec",
    }
    required = {
        "ka_doctor",
        "ka_status",
        "ka_tool_schema",
        "ka_skill_search",
        "ka_skill_load",
        "ka_record_user_requirement",
        "ka_checkpoint",
        "ka_resume_brief",
        "ka_pack_delta",
        "ka_context_pack",
    }

    assert names.isdisjoint(forbidden), sorted(names & forbidden)
    assert required <= names, sorted(required - names)


def test_goal_profile_is_sunset_alias_without_stage_filter():
    goal = tools_list_payload({"profile": "goal"})
    experiment = tools_list_payload({"profile": "goal", "stage": "experiment"})

    assert _names(goal) == _names(experiment)
    assert "profile_deprecated" in _warnings_text(goal)
    assert "profile_deprecated" in _warnings_text(experiment)
    assert experiment.get("stage_label") == "experiment"
    assert experiment.get("stage") in {None, "experiment"}


def test_unknown_stage_does_not_fail_closed_as_route_gate():
    base = tools_list_payload({"profile": "evidence"})
    staged = tools_list_payload({"profile": "evidence", "stage": "badstage"})

    assert staged.get("ok") is True, staged
    assert staged.get("error_type") != "unknown_stage"
    assert _names(staged) == _names(base)
    assert staged.get("stage_label") == "badstage"


def test_literature_profile_contains_paper_reliability_and_default_does_not():
    default_names = _names(tools_list_payload({}))
    evidence_names = _names(tools_list_payload({"profile": "evidence"}))
    literature_names = _names(tools_list_payload({"profile": "literature"}))

    literature_only = {
        "ka_strict_research_prepare",
        "ka_paper_fetch",
        "ka_record_literature_reading_note",
        "ka_paper_reliability_verify",
    }

    assert default_names.isdisjoint(literature_only)
    assert evidence_names.isdisjoint(literature_only)
    assert literature_only <= literature_names, sorted(literature_only - literature_names)
