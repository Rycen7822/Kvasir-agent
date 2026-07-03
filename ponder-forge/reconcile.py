from __future__ import annotations

import time

try:
    from .delegation import build_child_context
    from .profiles import get_profile
    from .store import PonderForgeStore
except ImportError:
    from delegation import build_child_context
    from profiles import get_profile
    from store import PonderForgeStore


def reconcile_run(store: PonderForgeStore, run_id: str, *, stale_after_seconds: int = 1800) -> dict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    now = time.time()
    marked_orphan: list[str] = []
    repaired: list[str] = []
    for task in store.list_rows("agent_tasks", run_id):
        if task.get("status") != "running":
            continue
        started = task.get("started_at")
        age = _age_seconds(started, now)
        if age >= stale_after_seconds:
            store.update_task_status(task["task_id"], "orphan", "stale running task")
            store.append_event(run_id, "task_orphaned", {"reason": "stale_running", "age_seconds": age}, task_id=task["task_id"])
            marked_orphan.append(task["task_id"])
    retry_tasks = [task for task in store.list_rows("agent_tasks", run_id) if task.get("status") == "orphan"]
    payload = _retry_payload(run_id, retry_tasks, run)
    return {
        "run_id": run_id,
        "repaired": repaired,
        "marked_orphan": marked_orphan,
        "delegate_task_payload_suggestion": payload,
    }


def _age_seconds(started_at: str | None, now: float) -> int:
    if not started_at:
        return 10**9
    try:
        return max(0, int(now - time.mktime(time.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ"))))
    except ValueError:
        return 10**9


def _retry_payload(run_id: str, tasks: list[dict], run: dict) -> dict:
    if not tasks:
        return {"tasks": []}
    payload_tasks = []
    profile = get_profile(str(run["profile"]))
    for task in tasks:
        marker = f"[PONDER_FORGE_RUN_ID={run_id}] [PONDER_FORGE_TASK_ID={task['task_id']}] [PONDER_FORGE_ROLE={task['role']}]"
        payload_tasks.append(
            {
                "goal": f"{marker} Retry orphaned task: {task['goal']}",
                "context": build_child_context(run, profile, task, retry=True),
                "role": "leaf",
            }
        )
    return {"tasks": payload_tasks}
