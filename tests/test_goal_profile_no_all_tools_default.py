from __future__ import annotations

from kvasir_agent.mcp.tool_registry import tools_list_payload
from kvasir_agent.profiles import DEFAULT_PROFILE_NAME, PROFILES, get_profile


def _names(payload: dict) -> set[str]:
    assert payload["ok"] is True, payload
    return {tool["name"] for tool in payload["tools"]}


def test_standard_discovery_lists_public_union_and_profiles_are_optional_filters():
    default_tools = _names(tools_list_payload())
    expected = {name for profile in PROFILES.values() if profile.registers_mcp for name in profile.tool_names}
    assert default_tools == expected
    assert {"ka_bash_exec", "ka_paper_record", "ka_environment"} <= default_tools
    assert {"ka_skill_search", "ka_skill_load", "ka_goal_context", "ka_goal_state", "ka_goal_next_action", "ka_context_pack"}.isdisjoint(default_tools)
    assert default_tools.isdisjoint(PROFILES["executor_local"].tool_names)
    core = _names(tools_list_payload({"profile": "core"}))
    assert core < default_tools
    assert core == set(get_profile("core").tool_names)
    goal = tools_list_payload({"profile": "goal"})
    assert _names(goal) == set(get_profile("evidence").tool_names)
    assert any("profile_deprecated" in warning for warning in goal["warnings"])


def test_stage_label_does_not_filter_tool_cards():
    goal = tools_list_payload({"profile": "goal"})
    experiment = tools_list_payload({"profile": "goal", "stage": "experiment"})

    assert len(goal["tools"]) < 48
    assert _names(experiment) == _names(goal)
    assert len(experiment["tools"]) == len(goal["tools"])
    assert goal["profile"] == "goal"
    assert experiment["stage_label"] == "experiment"
    assert "stage_label_not_used_for_tool_filtering" in experiment["warnings"]
    assert goal["compact"] is False
    assert experiment["compact"] is False
