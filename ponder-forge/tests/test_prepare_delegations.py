from __future__ import annotations

import importlib.util
import json
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


def _start_and_plan(
    goal: str,
    profile: str = "auto",
    *,
    budget: dict | None = None,
    constraints: list[str] | None = None,
):
    start = start_run(goal, profile=profile, budget=budget or {}, constraints=constraints or [])
    store = _store()
    plan = plan_run(store, start["run_id"])
    return store, start, plan


def _kind(task: dict) -> str:
    return json.loads(task.get("raw_json") or "{}").get("swarm", {}).get("kind", "")


def test_prepare_delegations_returns_lane_orchestrator_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, start, plan = _start_and_plan(
        "fix failing pytest in store.py using project alpha context",
        budget={"top_level_runs": 2, "child_concurrency_per_lane": 3},
        constraints=["do not modify external fixture alpha"],
    )

    prepared = prepare_delegations(store, start["run_id"])

    assert prepared["native_tool_to_call_next"] == "delegate_task"
    payload = prepared["delegate_task_payload"]
    payload_tasks = payload["tasks"]
    lanes = [task for task in plan["tasks"] if _kind(task) == "lane_coordinator"]
    children = [task for task in plan["tasks"] if _kind(task) == "lane_child"]
    assert set(payload) == {"tasks"}
    assert len(payload_tasks) == len(lanes) == 2
    assert children
    for task in payload_tasks:
        assert set(task) == {"goal", "context", "role"}
        assert task["role"] == "orchestrator"
        assert "toolsets" not in task
        assert "[PONDER_FORGE_RUN_ID=" in task["goal"]
        assert "[PONDER_FORGE_TASK_ID=" in task["goal"]
        assert "[PONDER_FORGE_ROLE=swarm_lane_coordinator]" in task["goal"]
        assert "[PONDER_FORGE_PROFILE=coding]" in task["context"]
        assert "You are a Ponder-Forge lane coordinator" in task["context"]
        assert "Immediately call native delegate_task" in task["context"]
        assert "at most 3 child subagents in flight" in task["context"]
        assert "child_reports" in task["context"]
        assert "Do not call the Ponder-Forge CLI" in task["context"]
        assert "project alpha context" in task["context"]
        assert "do not modify external fixture alpha" in task["context"]
        assert "ponder_forge_" not in task["context"]


def test_prepare_delegations_is_idempotent_for_queued_lane_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, start, _plan = _start_and_plan(
        "analyze csv metrics",
        budget={"top_level_runs": 1, "child_concurrency_per_lane": 2},
    )

    first = prepare_delegations(store, start["run_id"])
    second = prepare_delegations(store, start["run_id"])

    assert first["delegate_task_payload"] == second["delegate_task_payload"]


def test_prepare_delegations_includes_lane_child_manifest_and_profile_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, start, plan = _start_and_plan(
        "analyze csv metrics",
        profile="analysis",
        budget={"top_level_runs": 1, "child_concurrency_per_lane": 4},
    )

    prepared = prepare_delegations(store, start["run_id"])

    context = prepared["delegate_task_payload"]["tasks"][0]["context"]
    child_ids = [task["task_id"] for task in plan["tasks"] if _kind(task) == "lane_child"]
    assert child_ids
    for child_id in child_ids:
        assert child_id in context
    assert "Child task manifest:" in context
    assert "Required evidence types:" in context
    assert "metric_output" in context
    assert "command" in context
    assert "exit_code" in context
    assert "Final lane response must contain a single valid JSON object" in context


def test_prepare_delegations_limits_parent_payload_to_delegate_batch_size(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, start, _plan = _start_and_plan(
        "research source notes",
        profile="research",
        budget={"top_level_runs": 5, "child_concurrency_per_lane": 1, "delegate_batch_size": 2},
    )

    prepared = prepare_delegations(store, start["run_id"])

    assert len(prepared["delegate_task_payload"]["tasks"]) == 2
    assert prepared["remaining_queued_tasks"] == 3
