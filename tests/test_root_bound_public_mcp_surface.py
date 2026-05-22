from __future__ import annotations

from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload
from codex_scientist.profiles import PROFILES


LIFECYCLE_TOOLS = {
    "cs_get_quest_state",
    "cs_set_active_quest",
    "cs_new_quest",
    "cs_manifest_init",
}

EXPECTED_CORE = {
    "cs_doctor",
    "cs_status",
    "cs_tool_schema",
    "cs_record_user_requirement",
    "cs_context_pack",
    "cs_resume_brief",
    "cs_checkpoint",
    "cs_pack_delta",
    "cs_skill_search",
    "cs_skill_load",
}


def _names(payload: dict) -> set[str]:
    assert payload["ok"] is True
    return {tool["name"] for tool in payload["tools"]}


def test_root_bound_core_profile_hides_lifecycle_tools_and_includes_skill_router():
    assert set(PROFILES["core"].tool_names) == EXPECTED_CORE
    assert LIFECYCLE_TOOLS.isdisjoint(PROFILES["core"].tool_names)
    assert "legacy_registry_admin" in PROFILES
    assert PROFILES["legacy_registry_admin"].registers_mcp is False


def test_registered_public_profiles_do_not_expose_lifecycle_or_manifest_init():
    for profile in PROFILES.values():
        if not profile.registers_mcp:
            continue
        names = _names(tools_list_payload({"profile": profile.name}))
        assert LIFECYCLE_TOOLS.isdisjoint(names), profile.name
    assert "cs_manifest_record_baseline" in _names(tools_list_payload({"profile": "evidence"}))
    assert "cs_manifest_validate" in _names(tools_list_payload({"profile": "evidence"}))


def test_public_root_bound_tool_schemas_do_not_require_quest_id():
    cases = {
        "cs_memory_write": {"title"},
        "cs_artifact_record": set(),
        "cs_submit_idea": {"title", "novelty_contract"},
        "cs_record_main_experiment": {"run_id"},
        "cs_environment_validate": {"env_id"},
        "cs_feedback_ingest": {"env_id", "trajectory_id", "run_id", "source_kind"},
        "cs_bash_exec": set(),
    }
    for tool_name, expected_domain_required in cases.items():
        schema = call_tool("cs_tool_schema", {"name": tool_name})["schema"]["input_schema"]
        required = set(schema.get("required") or [])
        assert "quest_id" not in required, tool_name
        assert expected_domain_required <= required, tool_name


def test_public_tool_list_required_context_keys_do_not_include_quest_id():
    for profile in PROFILES.values():
        if not profile.registers_mcp:
            continue
        payload = tools_list_payload({"profile": profile.name})
        for tool in payload["tools"]:
            assert "quest_id" not in set(tool.get("required_context_keys") or []), tool["name"]
