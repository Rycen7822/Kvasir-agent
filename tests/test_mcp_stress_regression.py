from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool, list_tool_specs, tools_list_payload

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FORBIDDEN_AGENT_CLI = ("scripts/csctl.py", "CLI fallback", "csctl")


def _run_stdio(raw_input: str) -> list[dict]:
    completed = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "cs_mcp.py")],
        cwd=PLUGIN_ROOT,
        input=raw_input,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


def _run_jsonrpc(messages: list[dict]) -> list[dict]:
    return _run_stdio("\n".join(json.dumps(message) for message in messages) + "\n")


def _assert_no_cli_leak(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for forbidden in FORBIDDEN_AGENT_CLI:
        assert forbidden not in text


def _quest_root(project: Path, quest_id: str = "Q1") -> Path:
    root = project / "CodexScientist" / "quests" / quest_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "quest.yaml").write_text(f"quest_id: {quest_id}\n", encoding="utf-8")
    return root


def test_stdio_jsonrpc_stress_subset_has_stable_protocol_responses():
    invalid = _run_stdio("{not-json}\n")
    assert invalid[0]["error"]["code"] == -32700

    responses = _run_jsonrpc(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"profile": "goal", "stage": "analysis"}},
            {"jsonrpc": "2.0", "id": 3, "method": "codexscientist/missing", "params": {}},
        ]
    )

    assert responses[0]["result"]["serverInfo"]["name"] == "codexscientist_mcp"
    analysis = responses[1]["result"]
    assert analysis["ok"] is True
    assert analysis["profile"] == "goal"
    assert analysis["stage"] == "analysis"
    assert {tool["name"] for tool in analysis["tools"]}
    assert responses[2]["error"]["code"] == -32601
    _assert_no_cli_leak(responses)


def test_profile_stage_and_schema_stress_subset_matches_upgrade6_contract():
    core = tools_list_payload()
    goal = tools_list_payload({"profile": "goal"})
    unknown_stage = tools_list_payload({"profile": "goal", "stage": "unknown-stage"})
    admin = tools_list_payload({"profile": "admin"})

    core_names = {tool["name"] for tool in core["tools"]}
    goal_names = {tool["name"] for tool in goal["tools"]}
    assert len(list_tool_specs()) == 11
    assert len(core["tools"]) == 11
    assert {"cs_feedback_ingest", "cs_trajectory_search", "cs_trajectory_show"} <= goal_names
    assert core_names.isdisjoint({"cs_feedback_ingest", "cs_trajectory_search", "cs_trajectory_show"})
    assert unknown_stage["ok"] is True
    assert unknown_stage["stage_label"] == "unknown-stage"
    assert {tool["name"] for tool in unknown_stage["tools"]} == {tool["name"] for tool in goal["tools"]}
    assert admin["ok"] is False
    assert admin["error_type"] == "profile_not_registered_for_mcp"
    assert "tools" not in admin

    full_schema = call_tool("cs_tool_schema", {"name": "cs_submit_idea"})
    registry_schema = call_tool("cs_tool_schema", {"name": "cs_status"})
    assert full_schema["ok"] is True
    assert full_schema["schema"]["name"] == "cs_submit_idea"
    assert "novelty_contract" in full_schema["schema"]["input_schema"]["required"]
    assert registry_schema["ok"] is True
    assert registry_schema["schema"]["name"] == "cs_status"
    assert registry_schema["schema"].get("mcp_registry_only") is True
    _assert_no_cli_leak([core, goal, unknown_stage, admin, full_schema, registry_schema])


def test_failure_envelope_stress_subset_has_no_tool_error_or_cli_leakage(tmp_path: Path):
    _quest_root(tmp_path)
    payloads = [
        call_tool("cs_trial_plan", {"project": str(tmp_path)}),
        call_tool("cs_manifest_init", {"project": str(tmp_path)}),
        call_tool("cs_missing_for_stress_regression", {"project": str(tmp_path)}),
        call_tool("cs_claim_gate", {"project": str(tmp_path), "quest_id": "Q1", "claim_id": "C1", "claim_text": "unsupported claim"}),
    ]

    expected = ["missing_argument", "missing_argument", "unknown_tool", "claim_gate_blocked"]
    for payload, error_type in zip(payloads, expected, strict=True):
        assert payload["ok"] is False
        assert payload["error_type"] == error_type
        assert payload["recoverable"] is True
        assert payload["mcp"] is True
        assert payload.get("suggested_next_action") or payload.get("next_call") or payload.get("retry_template")
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        assert "tool_error" not in rendered
        assert "FileNotFoundError" not in rendered
        assert "ValueError" not in rendered
    assert payloads[-1]["error_family"] == "gate_blocked"
    _assert_no_cli_leak(payloads)
