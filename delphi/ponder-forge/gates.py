"""The source task-board completion gate; it does not certify claim correctness."""
from __future__ import annotations
try:
    from .planner import task_board
except ImportError:
    from planner import task_board


def evaluate_gate(store, run_id: str) -> dict:
    if not store.get_run(run_id):
        raise ValueError(f"unknown run_id: {run_id}")
    board = task_board(store, run_id)
    pending = [x for x in board if x["resolution"] not in {"resolved", "cancelled"}]
    return {"run_id": run_id, "pass": not pending, "pending_tasks": pending,
            "task_board": board, "scope": "research task resolutions; not scientific verification"}
