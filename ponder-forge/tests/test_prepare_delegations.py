from __future__ import annotations

import importlib.util
from pathlib import Path

from delegation import prepare_delegations
from planner import plan_run
from store import PonderForgeStore

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    spec = importlib.util.spec_from_file_location("ponder_forge_cli_prepare_test", ROOT / "cli.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


start_run = _load_cli().start_run


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def _start_and_plan(goal: str, profile: str = "auto", *, max_tasks_per_wave: int | None = None, constraints: list[str] | None = None):
    budget = {"max_tasks_per_wave": max_tasks_per_wave} if max_tasks_per_wave is not None else {}
    start = start_run(goal, profile=profile, budget=budget, constraints=constraints or [])
    store = _store()
    plan = plan_run(store, start["run_id"])
    return store, start, plan


def test_prepare_delegations_returns_native_delegate_task_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, start, plan = _start_and_plan(
        "fix failing pytest in store.py using project alpha context",
        max_tasks_per_wave=2,
        constraints=["do not modify external fixture alpha"],
    )

    prepared = prepare_delegations(store, start["run_id"])

    assert prepared["native_tool_to_call_next"] == "delegate_task"
    payload = prepared["delegate_task_payload"]
    assert set(payload) == {"tasks"}
    assert len(payload["tasks"]) == len(plan["tasks"]) == 2
    for task in payload["tasks"]:
        assert set(task) == {"goal", "context", "role"}
        assert task["role"] == "leaf"
        assert "toolsets" not in task
        assert "[PONDER_FORGE_RUN_ID=" in task["goal"]
        assert "[PONDER_FORGE_TASK_ID=" in task["goal"]
        assert "[PONDER_FORGE_ROLE=" in task["goal"]
        assert "[PONDER_FORGE_PROFILE=coding]" in task["context"]
        assert "project alpha context" in task["context"]
        assert "do not modify external fixture alpha" in task["context"]
        assert "Return a structured JSON report to the parent/controller" in task["context"]
        assert "parent/controller submits your JSON report" in task["context"]
        assert "ponder_forge_" not in task["context"]


def test_prepare_delegations_is_idempotent_for_queued_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, start, _plan = _start_and_plan("analyze csv metrics", max_tasks_per_wave=1)

    first = prepare_delegations(store, start["run_id"])
    second = prepare_delegations(store, start["run_id"])

    assert first["delegate_task_payload"] == second["delegate_task_payload"]


def test_prepare_delegations_exposes_analysis_metric_command_requirement(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, start, _plan = _start_and_plan("analyze csv metrics", profile="analysis")

    prepared = prepare_delegations(store, start["run_id"])

    contexts = [task["context"] for task in prepared["delegate_task_payload"]["tasks"]]
    assert contexts
    assert all("metric_output" in context and "command" in context for context in contexts)


def test_prepare_delegations_includes_child_report_contract_and_role_guidance(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, start, _plan = _start_and_plan("analyze csv metrics", profile="analysis", max_tasks_per_wave=5)

    prepared = prepare_delegations(store, start["run_id"])

    payload_tasks = prepared["delegate_task_payload"]["tasks"]
    contexts_by_role = {
        task["goal"].split("[PONDER_FORGE_ROLE=")[1].split("]")[0]: task["context"]
        for task in payload_tasks
    }
    assert {"data_inspector", "metric_analyst"} <= set(contexts_by_role)
    for context in contexts_by_role.values():
        assert context.count("Required evidence types:") == 1
        assert "Child report JSON contract:" in context
        assert '"assertions"' in context
        assert '"evidence"' in context
        assert '"artifacts"' in context
        assert "assertion_type" in context
        assert "data_result" in context
        assert "critical" in context
        assert "metric_output" in context
        assert "command" in context
        assert "exit_code" in context
        assert "reproduction_log" in context or "transform_script" in context
        assert "Final response must contain a single valid JSON object" in context
    assert "Role duty: inventory datasets" in contexts_by_role["data_inspector"]
    assert "Role duty: recompute or extract key metrics" in contexts_by_role["metric_analyst"]
