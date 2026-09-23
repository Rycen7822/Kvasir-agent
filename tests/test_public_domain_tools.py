from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from kvasir_agent.mcp.public_tools import OPERATIONS, PUBLIC_NAMES
from kvasir_agent.mcp.server import handle_jsonrpc_message
from kvasir_agent.mcp.tool_registry import call_tool, tools_list_payload


def invoke(project: Path, name: str, **arguments):
    response = handle_jsonrpc_message({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": {"project": str(project), **arguments}},
    })
    return response["result"]["structuredContent"]


def test_public_catalog_is_canonical_and_complete():
    tools = tools_list_payload()["tools"]
    assert {tool["name"] for tool in tools} == PUBLIC_NAMES
    assert len(tools) == 24
    for tool in tools:
        schema = tool["inputSchema"]
        Draft202012Validator.check_schema(schema)
        assert "project" in schema["required"]
        assert not {"quest_id", "project_root"} & schema["properties"].keys()
        assert schema["additionalProperties"] is False
    # Stable byte-size gate requires no model tokenizer dependency.
    assert len(json.dumps(tools, separators=(",", ":"))) < 32000


@pytest.mark.parametrize("name", [
    "ka_doctor", "ka_tool_schema", "ka_refresh_summary", "ka_get_method_scoreboard",
    "ka_get_optimization_frontier", "ka_arxiv", "ka_evolutionary_plan_round",
    "ka_strict_research_record_candidate", "ka_memory_search", "ka_confirm_baseline",
])
def test_retired_public_names_cannot_execute(tmp_path, name):
    result = invoke(tmp_path, name)
    assert result["ok"] is False
    assert result["error_type"] == "tool_not_registered_for_mcp"
    assert not (tmp_path / "Kvasir-agent").exists()


@pytest.mark.parametrize("arguments", [
    {"operation": "unknown"},
    {"operation": "idea", "title": "Missing contract"},
    {"operation": "result", "idea_id": "i1", "metric_delta": "bad-number"},
    {"operation": "negative", "idea_id": "i1", "title": "from wrong operation"},
    {"operation": "negative", "idea_id": "i1", "quest_id": "foreign"},
    {"operation": "negative", "idea_id": "i1", "project_root": "/foreign"},
])
def test_invalid_operation_arguments_do_not_write(tmp_path, arguments):
    result = invoke(tmp_path, "ka_method_record", **arguments)
    assert result["ok"] is False
    assert result["error_type"] in {"invalid_operation", "invalid_argument"}
    assert not (tmp_path / "Kvasir-agent").exists()


def test_method_updates_are_read_from_same_files_without_rewriting(tmp_path):
    assert invoke(tmp_path, "ka_record_user_requirement", message="Keep evaluator fixed")["ok"]
    result = invoke(tmp_path, "ka_method_record", operation="result", idea_id="method-a",
                    outcome="improved", metric_delta=0.2)
    assert result["ok"], result
    paths = [tmp_path / "Kvasir-agent/method_memory" / part
             for part in ("scoreboard/scoreboard.json", "frontier/frontier.json")]
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
    read = invoke(tmp_path, "ka_research_read", operation="methods")
    assert read["ok"], read
    assert read["scoreboard"]["ideas"][0]["idea_id"] == "method-a"
    assert read["frontier"]
    assert before == [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
    assert not (tmp_path / "Kvasir-agent/artifacts/method_scoreboard.json").exists()


def test_summary_refresh_cannot_overwrite_existing_text(tmp_path):
    root = tmp_path / "Kvasir-agent"
    root.mkdir()
    summary = root / "SUMMARY.md"
    summary.write_text("Research evidence must survive\n")
    result = call_tool("ka_refresh_summary", {"project": str(tmp_path)})
    assert result["ok"] is False
    assert summary.read_text() == "Research evidence must survive\n"


def test_requirements_memory_and_project_isolation(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for project in (a, b):
        assert invoke(project, "ka_record_user_requirement", message=project.name)["ok"]
    wrote = invoke(a, "ka_memory_write", title="Unique alpha evidence", content="alpha only")
    assert wrote["ok"], wrote
    found = invoke(a, "ka_memory_query", operation="search", query="alpha")
    other = invoke(b, "ka_memory_query", operation="search", query="alpha")
    assert found["ok"] and other["ok"], (found, other)
    assert "Unique alpha evidence" in json.dumps(found)
    assert "Unique alpha evidence" not in json.dumps(other)
    resume = invoke(a, "ka_research_read", operation="resume")
    assert resume["ok"], resume


def test_formal_run_and_novelty_guards_are_still_enforced(tmp_path):
    assert invoke(tmp_path, "ka_record_user_requirement", message="Research")["ok"]
    result = invoke(tmp_path, "ka_bash_exec", command="touch should-not-exist", operation="run")
    assert result["ok"] is False
    assert not (tmp_path / "should-not-exist").exists()
    result = invoke(tmp_path, "ka_method_record", operation="idea", title="Unproven idea",
                    novelty_contract={"mechanism": "x", "related_work_refs": [], "expected_difference": "y"})
    assert result["ok"] is False


def test_mixed_operation_tools_have_conservative_annotations():
    tools = {t["name"]: t for t in tools_list_payload()["tools"]}
    for name in ("ka_baseline", "ka_environment", "ka_method_record", "ka_analysis",
                 "ka_literature_setup", "ka_paper_record"):
        assert tools[name]["annotations"]["readOnlyHint"] is False
    for name in ("ka_research_read", "ka_memory_query", "ka_trajectory_query"):
        assert tools[name]["annotations"]["readOnlyHint"] is True


def test_public_environment_feedback_keeps_protected_hash_checks(tmp_path):
    from test_upgrade7_mcp_environment_trajectory import _toy_manifest
    from kvasir_agent.services.manifest import ManifestService
    from kvasir_agent.services.project_state import ProjectLayout

    assert invoke(tmp_path, "ka_record_user_requirement", message="Protect evaluator")["ok"]
    identity = ManifestService(ProjectLayout.from_project_root(tmp_path)).quest_identity()
    manifest = _toy_manifest(tmp_path, quest_id=identity["quest_id"])
    registered = invoke(tmp_path, "ka_environment", operation="register", manifest=manifest)
    assert registered["ok"], registered
    assert invoke(tmp_path, "ka_environment", operation="validate", env_id=manifest["env_id"])["ok"]
    created = invoke(tmp_path, "ka_trajectory_record", env_id=manifest["env_id"],
                     idea={"idea_id": "I1", "title": "Candidate", "mechanism_family": "toy"})
    assert created["ok"], created
    metrics = tmp_path / "metrics.json"
    metrics.write_text('{"metrics":{"score":0.6}}')
    feedback = dict(env_id=manifest["env_id"], trajectory_id=created["trajectory_id"],
                    run_id="R1", source_kind="local_metrics", metrics_path=str(metrics))
    accepted = invoke(tmp_path, "ka_feedback_ingest", **feedback)
    assert accepted["ok"], accepted
    (tmp_path / "src/eval.py").write_text("tampered")
    blocked = invoke(tmp_path, "ka_feedback_ingest", **{**feedback, "run_id": "R2"})
    assert blocked["ok"] is False
    assert "protect" in json.dumps(blocked).lower() or "hash" in json.dumps(blocked).lower()


def test_public_baseline_analysis_and_claim_flow(tmp_path):
    assert invoke(tmp_path, "ka_record_user_requirement", message="Measured evidence")["ok"]
    baseline = invoke(tmp_path, "ka_baseline", operation="create", baseline_id="b1")
    assert baseline["ok"], baseline
    confirm = {k: v for k, v in baseline["confirm_args"].items()
               if k not in {"quest_id", "project_root", "project"}}
    confirmed = invoke(tmp_path, "ka_baseline", operation="confirm", **confirm)
    assert confirmed["ok"], confirmed
    campaign = invoke(tmp_path, "ka_analysis", operation="create", campaign_title="Evidence",
                      campaign_goal="Check result", slices=[{"slice_id": "S1", "title": "Seed analysis"}])
    assert campaign["ok"], campaign
    campaign_id = campaign["campaign_id"]
    recorded = invoke(tmp_path, "ka_analysis", operation="record_slice", campaign_id=campaign_id,
                      slice_id="S1", status="completed", results="score=0.6")
    assert recorded["ok"], recorded
    read = invoke(tmp_path, "ka_analysis", operation="read", campaign_id=campaign_id)
    assert read["ok"], read
    evidence = tmp_path / "metric.json"
    evidence.write_text('{"score":0.6}')
    gate = invoke(tmp_path, "ka_claim_gate", claim_id="C1", baseline_id="b1", metric_contract="score",
                  evidence_paths=[str(evidence)], analysis_slice_ids=["S1"], seed_count=3)
    assert gate["ok"], gate
    assert gate["claim_gate"]["evidence_complete"] is True
    assert gate["claim_gate"]["scientific_validity"] == "not_assessed"
