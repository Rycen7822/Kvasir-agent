from __future__ import annotations

from codex_scientist.mcp.tool_registry import tools_list_payload
from codex_scientist.profiles import DEFAULT_PROFILE_NAME, PROFILES, get_profile


def test_default_profile_is_core_not_all_tools():
    assert DEFAULT_PROFILE_NAME == "core"
    default_profile = get_profile(None)
    goal_profile = get_profile("goal")

    assert default_profile.name == "core"
    assert goal_profile.name == "goal"
    assert len(default_profile.tool_names) < len(goal_profile.tool_names)
    assert "all" not in PROFILES or not PROFILES["all"].registers_mcp

    default_tools = {tool["name"] for tool in tools_list_payload()["tools"]}
    goal_tools = {tool["name"] for tool in tools_list_payload({"profile": "goal"})["tools"]}

    assert default_tools == set(default_profile.tool_names)
    assert "cs_bash_exec" not in default_tools
    assert "cs_submit_paper_bundle" not in default_tools
    assert "cs_bash_exec" in goal_tools
    assert "cs_submit_idea" in goal_tools
    assert goal_tools.issuperset(default_tools)


def test_stage_budget_keeps_tool_cards_bounded():
    goal = tools_list_payload({"profile": "goal"})
    experiment = tools_list_payload({"profile": "goal", "stage": "experiment"})

    assert len(goal["tools"]) < 48
    assert len(experiment["tools"]) < len(goal["tools"])
    assert len(experiment["tools"]) < 24
    assert goal["profile"] == "goal"
    assert experiment["stage"] == "experiment"
    assert goal["compact"] is True
    assert experiment["compact"] is True
