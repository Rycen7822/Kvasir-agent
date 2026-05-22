from __future__ import annotations

import json

from codex_scientist.mcp.tool_registry import tools_list_payload


def _names(payload: dict) -> set[str]:
    assert payload.get("ok") is True, payload
    return {tool["name"] for tool in payload.get("tools", [])}


def _warnings_text(payload: dict) -> str:
    return json.dumps(payload.get("warnings", []), ensure_ascii=False, sort_keys=True)


def test_default_core_surface_has_no_planner_or_execution_tools():
    names = _names(tools_list_payload({}))

    forbidden = {
        "cs_goal_context",
        "cs_goal_state",
        "cs_goal_next_action",
        "cs_goal_watchdog",
        "cs_queue_submit",
        "cs_queue_status",
        "cs_runner_start",
        "cs_runner_status",
        "cs_trial_propose",
        "cs_trial_plan",
        "cs_trial_ready",
        "cs_trial_evaluate",
        "cs_trial_decide",
        "cs_select_next_idea",
        "cs_bash_exec",
    }
    required = {
        "cs_doctor",
        "cs_status",
        "cs_tool_schema",
        "cs_skill_search",
        "cs_skill_load",
        "cs_record_user_requirement",
        "cs_checkpoint",
        "cs_resume_brief",
        "cs_pack_delta",
        "cs_context_pack",
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
        "cs_strict_research_prepare",
        "cs_paper_fetch",
        "cs_record_literature_reading_note",
        "cs_paper_reliability_verify",
    }

    assert default_names.isdisjoint(literature_only)
    assert evidence_names.isdisjoint(literature_only)
    assert literature_only <= literature_names, sorted(literature_only - literature_names)
