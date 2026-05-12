from __future__ import annotations

from codex_scientist.mcp.tool_registry import call_tool, list_tool_specs


def test_mcp_tool_specs_include_safety_annotations():
    for spec in list_tool_specs():
        data = spec.as_dict()
        annotations = data["annotations"]
        assert set(annotations) == {
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        }
        assert isinstance(annotations["readOnlyHint"], bool)
        assert isinstance(annotations["destructiveHint"], bool)
        assert isinstance(annotations["idempotentHint"], bool)
        assert isinstance(annotations["openWorldHint"], bool)


def test_mcp_annotations_mark_state_writing_tools_as_not_read_only():
    specs = {spec.name: spec.as_dict()["annotations"] for spec in list_tool_specs()}

    for name in [
        "cs_doctor",
        "cs_context_pack",
        "cs_manifest_validate",
        "cs_queue_reconcile",
        "cs_soak_accelerated",
        "cs_soak_crash_resume",
    ]:
        assert specs[name]["readOnlyHint"] is False

    for name in ["cs_status", "cs_trial_show", "cs_runner_status", "cs_queue_status", "cs_skill_search", "cs_skill_load"]:
        assert specs[name]["readOnlyHint"] is True


def test_mcp_unknown_tool_returns_structured_actionable_error():
    payload = call_tool("cs_missing_tool", {})

    assert payload["ok"] is False
    assert payload["error_type"] == "unknown_tool"
    assert payload["recoverable"] is True
    assert "suggested_next_action" in payload
