from __future__ import annotations

import importlib.util
from pathlib import Path

import planner
from gates import evaluate_gate
from planner import plan_run
from reconcile import reconcile_run
from store import PonderForgeStore

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    spec = importlib.util.spec_from_file_location("ponder_forge_cli_reconcile_test", ROOT / "cli.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLI = _load_cli()


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def test_reconcile_marks_stale_running_task_orphan(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(
        planner,
        "derive_lane_child_specs",
        lambda _run, _profile, _lane_index: [
            {"role": "data_analyst", "goal": "summarize data result", "context": "data_result required"},
            {"role": "metric_checker", "goal": "verify metric output", "context": "metric_output required"},
        ],
    )
    start = CLI.start_run(
        "analyze experiment metrics",
        profile="analysis",
        budget={"top_level_runs": 1, "child_concurrency_per_lane": 2},
    )
    store = _store()
    plan = plan_run(store, start["run_id"])
    task = next(task for task in plan["tasks"] if task["role"] == "swarm_lane_coordinator")
    store.update_task_binding(task["task_id"], child_session_id="stale", subagent_id="sub-stale", status="running")

    result = reconcile_run(store, start["run_id"], stale_after_seconds=0)

    assert result["marked_orphan"] == [task["task_id"]]
    retry = result["delegate_task_payload_suggestion"]
    assert retry["tasks"]
    assert task["task_id"] in retry["tasks"][0]["goal"]
    assert retry["tasks"][0]["role"] == "orchestrator"
    retry_context = retry["tasks"][0]["context"]
    assert "Retry context" in retry_context
    assert "child_reports" in retry_context
    assert "Child task manifest:" in retry_context
    assert "data_result" in retry_context
    assert "metric_output" in retry_context
    assert "command" in retry_context
    assert "exit_code" in retry_context


def test_reconcile_keeps_non_lane_orphan_retry_leaf(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = CLI.start_run("research source notes", profile="research")
    store = _store()
    task = store.create_task(
        start["run_id"],
        role="independent_reviewer",
        goal="review one assertion",
        status="running",
    )

    result = reconcile_run(store, start["run_id"], stale_after_seconds=0)

    assert result["marked_orphan"] == [task["task_id"]]
    retry = result["delegate_task_payload_suggestion"]
    assert retry["tasks"][0]["role"] == "leaf"
    assert "Retry context" in retry["tasks"][0]["context"]


def test_obsolete_tool_hook_schema_adapters_are_removed():
    for rel in ("tools.py", "schemas.py", "hooks.py", "role_policy.py"):
        assert not (ROOT / rel).exists()


def test_reconcile_rejects_unknown_run_id(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = _store()

    try:
        reconcile_run(store, "pf_run_missing", stale_after_seconds=0)
    except ValueError as exc:
        assert "unknown run_id: pf_run_missing" in str(exc)
    else:
        raise AssertionError("reconcile_run should reject unknown run ids")


def test_reconcile_creates_gate_gap_repair_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = CLI.start_run("analyze experiment metrics", profile="analysis")
    store = _store()
    report = store.create_report(
        run_id=start["run_id"],
        task_id="producer-task",
        role="metric_analyst",
        title="thin report",
        summary="unsupported claim",
    )
    assertion = store.create_assertion(
        run_id=start["run_id"],
        report_id=report["report_id"],
        profile="analysis",
        assertion_type="data_result",
        text="Stage10 gates all pass",
        importance=0.95,
        raw={"critical": True},
    )

    result = reconcile_run(store, start["run_id"], stale_after_seconds=0)

    assert result["marked_orphan"] == []
    assert result["gate_status"] == "blocked"
    assert result["gate_gap_task_count"] == 1
    retry = result["delegate_task_payload_suggestion"]
    assert len(retry["tasks"]) == 1
    task = retry["tasks"][0]
    assert task["role"] == "leaf"
    assert assertion["assertion_id"] in task["goal"]
    assert "missing_profile_evidence" in task["context"]
    assert "metric_output.command" in task["context"]
    assert "exit_code=0" in task["context"]
    assert '"artifacts": []' in task["context"]
    repair_tasks = [row for row in store.list_rows("agent_tasks", start["run_id"]) if row["role"] == "gate_gap_repairer"]
    assert len(repair_tasks) == 1
    stored_task = repair_tasks[0]
    assert stored_task["task_id"] in task["goal"]
    assert f"repair_task_id={stored_task['task_id']}" in task["context"]
    assert set(task) == {"goal", "context", "role"}
    assert stored_task["status"] == "queued"
    fetched_task = store.get_task(stored_task["task_id"])
    assert fetched_task is not None
    assert fetched_task["role"] == "gate_gap_repairer"
    assert store.list_rows("assertions", start["run_id"])[0]["status"] == "needs_revision"

    second = reconcile_run(store, start["run_id"], stale_after_seconds=0)

    assert second["gate_gap_task_count"] == 1
    second_task = second["delegate_task_payload_suggestion"]["tasks"][0]
    assert stored_task["task_id"] in second_task["goal"]


def test_gate_gap_repair_tasks_block_finalize_until_finished(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = CLI.start_run("analyze experiment metrics", profile="analysis")
    store = _store()
    supported_report = store.create_report(
        run_id=start["run_id"],
        task_id="supported-producer",
        role="metric_analyst",
        title="supported report",
        summary="supported claim",
    )
    supported_assertion = store.create_assertion(
        run_id=start["run_id"],
        report_id=supported_report["report_id"],
        profile="analysis",
        assertion_type="data_result",
        text="supported Stage10 metric",
        importance=0.95,
        raw={"critical": True},
    )
    store.create_evidence(
        run_id=start["run_id"],
        report_id=supported_report["report_id"],
        assertion_id=supported_assertion["assertion_id"],
        evidence_type="metric_output",
        source_ref="metrics.json",
        command="python eval.py",
        exit_code=0,
    )
    store.create_evidence(
        run_id=start["run_id"],
        report_id=supported_report["report_id"],
        assertion_id=supported_assertion["assertion_id"],
        evidence_type="transform_script",
        source_ref="eval.py",
    )
    store.create_evidence(
        run_id=start["run_id"],
        report_id=supported_report["report_id"],
        assertion_id=supported_assertion["assertion_id"],
        evidence_type="sanity_check",
        source_ref="sanity.log",
    )
    reviewer = store.create_task(start["run_id"], role="repro_reviewer", goal="review supported", parent_task_id="supported-producer")
    store.create_verdict(
        run_id=start["run_id"],
        profile="analysis",
        target_type="assertion",
        target_id=supported_assertion["assertion_id"],
        reviewer_role="repro_reviewer",
        reviewer_task_id=reviewer["task_id"],
        verifier_mode="independent_review",
        independent_from_task_id="supported-producer",
        verdict="accept",
    )
    store.update_assertion_status(supported_assertion["assertion_id"], "accepted")
    thin_report = store.create_report(
        run_id=start["run_id"],
        task_id="thin-producer",
        role="metric_analyst",
        title="thin report",
        summary="unsupported claim",
    )
    store.create_assertion(
        run_id=start["run_id"],
        report_id=thin_report["report_id"],
        profile="analysis",
        assertion_type="data_result",
        text="unsupported Stage10 metric",
        importance=0.95,
        raw={"critical": True},
    )

    reconcile_run(store, start["run_id"], stale_after_seconds=0)
    gate = evaluate_gate(store, start["run_id"])

    assert gate["status"] == "blocked"
    assert any(gap.get("gap_type") == "incomplete_gate_gap_repairs" for gap in gate["gaps"])
