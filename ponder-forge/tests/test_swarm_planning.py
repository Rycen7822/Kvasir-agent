from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from planner import plan_run
from store import PonderForgeStore

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    spec = importlib.util.spec_from_file_location("ponder_forge_cli_swarm_plan_test", ROOT / "cli.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLI = _load_cli()


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def _kind(task: dict) -> str:
    return json.loads(task.get("raw_json") or "{}").get("swarm", {}).get("kind", "")


def test_plan_defaults_to_eight_lanes_and_four_way_child_concurrency(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = CLI.start_run("research source notes", profile="research")
    store = _store()

    plan = plan_run(store, start["run_id"])

    tasks = plan["tasks"]
    lanes = [task for task in tasks if _kind(task) == "lane_coordinator"]
    children = [task for task in tasks if _kind(task) == "lane_child"]
    assert len(lanes) == 8
    assert children
    assert {task["status"] for task in lanes} == {"queued"}
    assert {task["status"] for task in children} == {"planned"}
    assert all(child["parent_task_id"] in {lane["task_id"] for lane in lanes} for child in children)
    assert {json.loads(task["raw_json"])["swarm"]["child_concurrency_limit"] for task in lanes} == {4}
    assert plan["swarm_budget"] == {
        "top_level_runs": 8,
        "child_concurrency_per_lane": 4,
        "delegate_batch_size": 20,
    }
    assert all("subagents_per_run" not in json.loads(task["raw_json"])["swarm"] for task in lanes)


def test_plan_budget_controls_lane_count_and_child_concurrency(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = CLI.start_run(
        "design architecture",
        profile="design",
        budget={"top_level_runs": 2, "child_concurrency_per_lane": 3},
    )
    store = _store()

    plan = plan_run(store, start["run_id"])

    lanes = [task for task in plan["tasks"] if _kind(task) == "lane_coordinator"]
    children = [task for task in plan["tasks"] if _kind(task) == "lane_child"]
    assert len(lanes) == 2
    assert children
    assert [json.loads(task["raw_json"])["swarm"]["lane_index"] for task in lanes] == [1, 2]
    assert {json.loads(task["raw_json"])["swarm"]["child_concurrency_limit"] for task in lanes} == {3}


def test_plan_child_backlog_is_not_limited_by_child_concurrency(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    def _three_child_specs(*_args, **_kwargs):
        return [
            {"role": "researcher", "goal": "child work 1"},
            {"role": "researcher", "goal": "child work 2"},
            {"role": "researcher", "goal": "child work 3"},
        ]

    monkeypatch.setattr("planner.derive_lane_child_specs", _three_child_specs)
    start = CLI.start_run(
        "research source notes",
        profile="research",
        budget={"top_level_runs": 1, "child_concurrency_per_lane": 1},
    )
    store = _store()

    plan = plan_run(store, start["run_id"])

    children = [task for task in plan["tasks"] if _kind(task) == "lane_child"]
    assert len(children) == 3
    assert {json.loads(task["raw_json"])["swarm"]["child_concurrency_limit"] for task in children} == {1}


def test_plan_is_idempotent_for_existing_swarm_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = CLI.start_run(
        "research source notes",
        profile="research",
        budget={"top_level_runs": 2, "child_concurrency_per_lane": 2},
    )
    store = _store()

    first = plan_run(store, start["run_id"])
    second = plan_run(store, start["run_id"])

    assert [task["task_id"] for task in first["tasks"]] == [task["task_id"] for task in second["tasks"]]
    assert len(second["tasks"]) == len(first["tasks"])
