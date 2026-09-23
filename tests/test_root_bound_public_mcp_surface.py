from __future__ import annotations

from kvasir_agent.mcp.tool_registry import call_tool, tools_list_payload
from kvasir_agent.profiles import PROFILES


LIFECYCLE_TOOLS = {
    "ka_get_quest_state",
    "ka_set_active_quest",
    "ka_new_quest",
    "ka_manifest_init",
}

EXPECTED_CORE = {"ka_research_read", "ka_record_user_requirement", "ka_checkpoint"}


def _names(payload: dict) -> set[str]:
    assert payload["ok"] is True
    return {tool["name"] for tool in payload["tools"]}


def test_root_bound_core_profile_hides_lifecycle_tools_and_uses_native_skill_discovery():
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
    assert "ka_baseline" in _names(tools_list_payload({"profile": "evidence"}))
    assert "ka_environment" in _names(tools_list_payload({"profile": "evidence"}))


def test_public_root_bound_tool_schemas_do_not_require_quest_id():
    cases = {
        "ka_memory_write": {"title"},
        "ka_artifact_record": set(),
        "ka_submit_idea": {"title", "novelty_contract"},
        "ka_record_main_experiment": {"run_id"},
        "ka_environment_validate": {"env_id"},
        "ka_feedback_ingest": {"env_id", "trajectory_id", "run_id", "source_kind"},
        "ka_bash_exec": set(),
    }
    for tool_name, expected_domain_required in cases.items():
        schema = call_tool("ka_tool_schema", {"name": tool_name})["schema"]["input_schema"]
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


def test_bundled_mcp_requires_absolute_project_before_writing(tmp_path, monkeypatch):
    from kvasir_agent.mcp.server import handle_jsonrpc_message

    cache = tmp_path / "plugin-cache"
    cache.mkdir()
    monkeypatch.chdir(cache)

    def record(arguments):
        response = handle_jsonrpc_message({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "ka_record_user_requirement", "arguments": {
                "message": "Keep the evaluator protected", **arguments,
            }},
        })
        return response["result"]["structuredContent"]

    for arguments in ({}, {"project": " "}, {"project": "."}, {"project": 42}):
        rejected = record(arguments)
        assert rejected["ok"] is False
        assert rejected["error_type"] == "missing_project_root"
        assert not (cache / "Kvasir-agent").exists()

    for key in ("project",):
        project = tmp_path / key
        accepted = record({key: str(project)})
        assert accepted["ok"] is True, accepted
        assert (project / "Kvasir-agent/research.yaml").is_file()
    assert record({"project_root": str(tmp_path)})["ok"] is False
    assert not (cache / "Kvasir-agent").exists()


def test_advertised_schemas_require_project_for_research_calls():
    for tool in tools_list_payload()["tools"]:
        schema = tool["inputSchema"]
        assert "project" in schema["required"]
        assert "project_root" not in schema["properties"]
