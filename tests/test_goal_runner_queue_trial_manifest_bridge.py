from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _assert_ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def test_manifest_queue_runner_trial_bridge_uses_mcp_service_handlers(tmp_path: Path):
    manifest = _assert_ok(call_tool("cs_manifest_init", {"project": str(tmp_path), "name": "bridge", "goal": "bridge goal"}))
    assert Path(manifest["path"]).is_file()
    assert Path(manifest["path"]).is_relative_to(tmp_path)

    baseline = _assert_ok(
        call_tool(
            "cs_manifest_record_baseline",
            {"project": str(tmp_path), "baseline_id": "base", "status": "confirmed", "metric_contract": "primary"},
        )
    )
    assert baseline["baseline_ready"] is True

    validation = _assert_ok(call_tool("cs_manifest_validate", {"project": str(tmp_path)}))
    assert validation["baseline_ready"] is True

    job = _assert_ok(call_tool("cs_queue_submit", {"project": str(tmp_path), "job_id": "job1", "command": "python train.py"}))
    assert job["job"]["job_id"] == "job1"
    assert job["job"]["status"] == "pending"

    run = _assert_ok(call_tool("cs_runner_start", {"project": str(tmp_path), "command": "python train.py", "job_id": "job1", "dry_run": True}))
    run_id = run["run"]["run_id"]
    status = _assert_ok(call_tool("cs_runner_status", {"project": str(tmp_path), "run_id": run_id}))
    assert status["run"]["run_id"] == run_id
    assert status["run"]["status"] == "dry_run"

    attempt = _assert_ok(
        call_tool(
            "cs_queue_start_attempt",
            {"project": str(tmp_path), "job_id": "job1", "dry_run": True, "expected_outputs": ["results.json"]},
        )
    )
    assert attempt["job"]["latest_run_id"]

    trial = _assert_ok(
        call_tool(
            "cs_trial_propose",
            {
                "project": str(tmp_path),
                "quest_id": "Q1",
                "idea_id": "I1",
                "hypothesis": "Bridge hypothesis",
                "mechanism": "Service-level trial wrapper",
            },
        )
    )
    trial_id = trial["trial"]["trial_id"]
    planned = _assert_ok(call_tool("cs_trial_plan", {"project": str(tmp_path), "trial_id": trial_id, "metric_contract_id": "primary", "novelty_decision": "pass"}))
    assert planned["trial"]["status"] == "planned"
    ready = _assert_ok(call_tool("cs_trial_ready", {"project": str(tmp_path), "trial_id": trial_id}))
    assert ready["trial"]["status"] == "ready"
    evaluated = _assert_ok(call_tool("cs_trial_evaluate", {"project": str(tmp_path), "trial_id": trial_id, "metric_values": {"primary": 1.0}, "artifacts": []}))
    assert evaluated["trial"]["status"] == "evaluated"
    decided = _assert_ok(call_tool("cs_trial_decide", {"project": str(tmp_path), "trial_id": trial_id, "decision": "keep", "reviewer_verdict": "pass"}))
    assert decided["trial"]["status"] == "kept"


def test_mcp_fail_closed_without_cli_suggestion():
    payload = call_tool("cs_missing_research_primitive", {})
    assert payload["ok"] is False
    assert payload["error_type"] == "unknown_tool"
    combined = json.dumps(payload, ensure_ascii=False)
    assert "scripts/csctl.py" not in combined
    assert "CLI fallback" not in combined
    assert "tools/list" in combined
