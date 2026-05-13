from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload

FORBIDDEN_AGENT_CLI = ("scripts/csctl.py", "CLI fallback", "csctl")


def assert_no_cli_guidance(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for forbidden in FORBIDDEN_AGENT_CLI:
        assert forbidden not in text


def assert_failure_envelope(payload: dict, *, expected_error_type: str, tool_name: str) -> None:
    assert payload["ok"] is False
    assert payload["error"]
    assert payload["error_type"] == expected_error_type, payload
    assert payload["recoverable"] is True, payload
    assert payload["tool"] == tool_name
    assert payload["mcp"] is True
    assert isinstance(payload.get("source_refs"), list)
    assert isinstance(payload.get("warnings"), list)
    assert payload.get("suggested_next_action") or payload.get("next_call") or payload.get("retry_template")
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert "tool_error" not in text
    assert "FileNotFoundError" not in text
    assert "ValueError" not in text
    assert_no_cli_guidance(payload)


def _state_root(project: Path) -> Path:
    return project / "CodexScientist"


def test_trial_lifecycle_missing_trial_id_returns_recoverable_contract(tmp_path: Path):
    for tool_name in ("cs_trial_plan", "cs_trial_ready", "cs_trial_evaluate", "cs_trial_decide"):
        payload = call_tool(tool_name, {"project": str(tmp_path)})

        assert payload["ok"] is False, tool_name
        assert payload["error_type"] == "missing_argument", payload
        assert payload["recoverable"] is True
        text = json.dumps(payload, ensure_ascii=False)
        assert "trial_id" in text
        assert "tool_error" not in text
        assert_no_cli_guidance(payload)


def test_trial_lifecycle_unknown_trial_id_returns_not_found_contract(tmp_path: Path):
    for tool_name in ("cs_trial_plan", "cs_trial_ready", "cs_trial_evaluate", "cs_trial_decide"):
        payload = call_tool(tool_name, {"project": str(tmp_path), "trial_id": "T9999"})

        assert payload["ok"] is False, tool_name
        assert payload["error_type"] == "not_found", payload
        assert payload["recoverable"] is True
        text = json.dumps(payload, ensure_ascii=False)
        assert "FileNotFoundError" not in text
        assert "tool_error" not in text
        assert "cs_trial_show" in text
        assert "cs_trial_propose" in text
        assert_no_cli_guidance(payload)


def test_required_state_changing_tools_fail_closed_without_required_args(tmp_path: Path):
    strict_tools = (
        "cs_manifest_init",
        "cs_manifest_record_baseline",
        "cs_queue_submit",
        "cs_runner_start",
        "cs_trial_propose",
    )
    for tool_name in strict_tools:
        before_paths = sorted(str(path.relative_to(tmp_path)) for path in _state_root(tmp_path).glob("**/*")) if _state_root(tmp_path).exists() else []
        payload = call_tool(tool_name, {"project": str(tmp_path)})
        after_paths = sorted(str(path.relative_to(tmp_path)) for path in _state_root(tmp_path).glob("**/*")) if _state_root(tmp_path).exists() else []

        assert payload["ok"] is False, (tool_name, payload)
        assert payload["error_type"] == "missing_argument", payload
        assert payload["recoverable"] is True
        assert payload.get("retry_template", {}).get("name") == tool_name
        next_call = payload.get("next_call") or {}
        assert next_call.get("name") != "cs_tool_schema"
        assert before_paths == after_paths
        assert_no_cli_guidance(payload)


def test_bash_exec_list_without_command_is_readonly_and_run_without_command_fails_closed(tmp_path: Path):
    list_payload = call_tool("cs_bash_exec", {"project": str(tmp_path), "quest_id": "Q1"})

    assert list_payload["ok"] is True
    list_text = json.dumps(list_payload, ensure_ascii=False).lower()
    assert "session" in list_text or "bash" in list_text
    assert_no_cli_guidance(list_payload)

    run_payload = call_tool(
        "cs_bash_exec",
        {"project": str(tmp_path), "quest_id": "Q1", "operation": "run"},
    )

    assert run_payload["ok"] is False
    assert run_payload["error_type"] == "missing_argument", run_payload
    assert run_payload["recoverable"] is True
    text = json.dumps(run_payload, ensure_ascii=False)
    assert "command" in text
    assert_no_cli_guidance(run_payload)


def test_goal_unknown_stage_is_label_only_and_does_not_filter_tools():
    payload = tools_list_payload({"profile": "goal", "stage": "unknown-stage"})

    assert payload["ok"] is True
    assert payload["stage"] == "unknown-stage"
    assert payload["stage_label"] == "unknown-stage"
    assert "stage_label_not_used_for_tool_filtering" in payload["warnings"]
    assert {tool["name"] for tool in payload["tools"]} == {tool["name"] for tool in tools_list_payload({"profile": "goal"})["tools"]}
    assert_no_cli_guidance(payload)


def test_admin_profile_is_not_agent_facing_tools_list():
    payload = tools_list_payload({"profile": "admin"})

    assert payload["ok"] is False
    assert payload["error_type"] == "profile_not_registered_for_mcp", payload
    assert payload["recoverable"] is True
    assert payload["profile"] == "admin"
    assert "tools" not in payload
    assert_no_cli_guidance(payload)


def test_known_recoverable_failures_use_stable_error_taxonomy(tmp_path: Path):
    missing_quest = call_tool("cs_get_analysis_campaign", {"project": str(tmp_path), "quest_id": "Q1"})
    assert_failure_envelope(missing_quest, expected_error_type="not_found", tool_name="cs_get_analysis_campaign")

    quest_root = tmp_path / "CodexScientist" / "quests" / "Q1"
    quest_root.mkdir(parents=True)
    (quest_root / "quest.yaml").write_text("quest_id: Q1\n", encoding="utf-8")

    missing_campaign = call_tool("cs_get_analysis_campaign", {"project": str(tmp_path), "quest_id": "Q1"})
    assert_failure_envelope(missing_campaign, expected_error_type="not_found", tool_name="cs_get_analysis_campaign")
    retry_template = missing_campaign.get("retry_template") or {}
    assert retry_template.get("name") == "cs_create_analysis_campaign"
    assert retry_template.get("required_arguments") == ["quest_id", "campaign_title", "campaign_goal", "slices"]
    assert retry_template.get("missing_arguments") == ["campaign_title", "campaign_goal", "slices"]
    assert retry_template.get("known_arguments") == {"quest_id": "Q1"}

    missing_quest_memory = call_tool("cs_memory_search", {"project": str(tmp_path), "query": "x", "kind": "bad-kind"})
    assert_failure_envelope(missing_quest_memory, expected_error_type="missing_argument", tool_name="cs_memory_search")
