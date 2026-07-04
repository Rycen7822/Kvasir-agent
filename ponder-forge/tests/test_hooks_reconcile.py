from __future__ import annotations

import importlib.util
from pathlib import Path

import planner
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
