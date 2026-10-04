from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

DEFAULT_TOP_LEVEL_RUNS = 8
DEFAULT_CHILD_CONCURRENCY_PER_LANE = 4
DEFAULT_DELEGATE_BATCH_SIZE = 20
RETIRED_BUDGET_KEYS = {"max_tasks_per_wave", "subagents_per_run"}
CANONICAL_BUDGET_KEYS = {"top_level_runs", "child_concurrency_per_lane", "delegate_batch_size"}


@dataclass(frozen=True)
class SwarmBudget:
    top_level_runs: int = DEFAULT_TOP_LEVEL_RUNS
    child_concurrency_per_lane: int = DEFAULT_CHILD_CONCURRENCY_PER_LANE
    delegate_batch_size: int = DEFAULT_DELEGATE_BATCH_SIZE

    def as_dict(self) -> dict[str, int]:
        return {
            "top_level_runs": self.top_level_runs,
            "child_concurrency_per_lane": self.child_concurrency_per_lane,
            "delegate_batch_size": self.delegate_batch_size,
        }


def _positive_int(value: Any, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"budget.{key} must be a positive integer")
    return value


def normalize_swarm_budget(raw: dict[str, Any] | None) -> SwarmBudget:
    budget = dict(raw or {})
    retired = sorted(RETIRED_BUDGET_KEYS & set(budget))
    if retired:
        raise ValueError(
            f"retired budget key: {retired[0]}; use top_level_runs and child_concurrency_per_lane"
        )
    unknown = sorted(set(budget) - CANONICAL_BUDGET_KEYS)
    if unknown:
        raise ValueError(f"unknown budget key: {unknown[0]}")
    return SwarmBudget(
        top_level_runs=_positive_int(budget.get("top_level_runs", DEFAULT_TOP_LEVEL_RUNS), "top_level_runs"),
        child_concurrency_per_lane=_positive_int(
            budget.get("child_concurrency_per_lane", DEFAULT_CHILD_CONCURRENCY_PER_LANE),
            "child_concurrency_per_lane",
        ),
        delegate_batch_size=_positive_int(
            budget.get("delegate_batch_size", DEFAULT_DELEGATE_BATCH_SIZE),
            "delegate_batch_size",
        ),
    )


def task_raw(row: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(row.get("raw_json") or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def task_swarm(row: dict[str, Any]) -> dict[str, Any]:
    value = task_raw(row).get("swarm")
    return value if isinstance(value, dict) else {}


def task_kind(row: dict[str, Any]) -> str:
    return str(task_swarm(row).get("kind") or "")


def swarm_topology_status(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    lanes = [task for task in tasks if task_kind(task) == "lane_coordinator"]
    children = [task for task in tasks if task_kind(task) == "lane_child"]
    incomplete = [task for task in (*lanes, *children) if task.get("status") != "finished"]
    return {
        "is_swarm_run": bool(lanes or children),
        "lane_count": len(lanes),
        "child_count": len(children),
        "finished_lane_count": sum(1 for task in lanes if task.get("status") == "finished"),
        "finished_child_count": sum(1 for task in children if task.get("status") == "finished"),
        "incomplete_task_ids": [str(task["task_id"]) for task in incomplete],
        "complete": not incomplete,
    }


def swarm_progress_status(tasks: list[dict[str, Any]], budget: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_swarm_budget(budget)
    topology = swarm_topology_status(tasks)
    queued_lanes = [
        task
        for task in tasks
        if task_kind(task) == "lane_coordinator" and task.get("status") == "queued"
    ]
    return {
        "is_swarm_run": topology["is_swarm_run"],
        "lane_count": topology["lane_count"],
        "lane_child_concurrency_limit": normalized.child_concurrency_per_lane,
        "child_count": topology["child_count"],
        "finished_lane_count": topology["finished_lane_count"],
        "finished_child_count": topology["finished_child_count"],
        "queued_delegation_count": len(queued_lanes),
        "incomplete_task_count": len(topology["incomplete_task_ids"]),
    }
