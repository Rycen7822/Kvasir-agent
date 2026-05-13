from __future__ import annotations

from codex_scientist.mcp.tool_registry import tools_list_payload
from codex_scientist.profiles import DEFAULT_PROFILE_NAME, PROFILES, get_profile


def _names(payload: dict) -> set[str]:
    assert payload["ok"] is True, payload
    return {tool["name"] for tool in payload["tools"]}


def test_default_profile_is_core_not_all_tools():
    assert DEFAULT_PROFILE_NAME == "core"
    default_profile = get_profile(None)
    goal_profile = get_profile("goal")
    evidence_profile = get_profile("evidence")

    assert default_profile.name == "core"
    assert goal_profile.name == "goal"
    assert goal_profile.deprecated
    assert set(goal_profile.tool_names) == set(evidence_profile.tool_names)
    assert len(default_profile.tool_names) < len(goal_profile.tool_names)
    assert "all" not in PROFILES or not PROFILES["all"].registers_mcp

    default_tools = _names(tools_list_payload())
    goal_payload = tools_list_payload({"profile": "goal"})
    goal_tools = _names(goal_payload)

    assert default_tools == set(default_profile.tool_names)
    assert "cs_bash_exec" not in default_tools
    assert "cs_submit_paper_bundle" not in default_tools
    assert "cs_bash_exec" not in goal_tools
    assert "cs_submit_idea" in goal_tools
    assert goal_tools.issuperset(default_tools)
    assert any("profile_deprecated" in warning for warning in goal_payload["warnings"])


def test_stage_label_does_not_filter_tool_cards():
    goal = tools_list_payload({"profile": "goal"})
    experiment = tools_list_payload({"profile": "goal", "stage": "experiment"})

    assert len(goal["tools"]) < 48
    assert _names(experiment) == _names(goal)
    assert len(experiment["tools"]) == len(goal["tools"])
    assert goal["profile"] == "goal"
    assert experiment["stage_label"] == "experiment"
    assert "stage_label_not_used_for_tool_filtering" in experiment["warnings"]
    assert goal["compact"] is True
    assert experiment["compact"] is True
