from __future__ import annotations

import json
import time

try:
    from .delegation import build_child_context, build_lane_context, lane_child_tasks
    from .gates import evaluate_gate
    from .profiles import get_profile
    from .store import PonderForgeStore
    from .swarm import task_kind
except ImportError:
    from delegation import build_child_context, build_lane_context, lane_child_tasks
    from gates import evaluate_gate
    from profiles import get_profile
    from store import PonderForgeStore
    from swarm import task_kind


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
    gate = evaluate_gate(store, run_id)
    gate_gap_tasks = _gate_gap_repair_tasks(store, run_id, run, gate)
    payload = _merge_payloads(_retry_payload(store, run_id, retry_tasks, run), _gate_gap_payload(run_id, run, gate_gap_tasks))
    return {
        "run_id": run_id,
        "repaired": repaired,
        "marked_orphan": marked_orphan,
        "gate_status": gate["status"],
        "gate_gap_task_count": len(gate_gap_tasks),
        "delegate_task_payload_suggestion": payload,
    }


def _age_seconds(started_at: str | None, now: float) -> int:
    if not started_at:
        return 10**9
    try:
        return max(0, int(now - time.mktime(time.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ"))))
    except ValueError:
        return 10**9


def _retry_payload(store: PonderForgeStore, run_id: str, tasks: list[dict], run: dict) -> dict:
    if not tasks:
        return {"tasks": []}
    payload_tasks = []
    profile = get_profile(str(run["profile"]))
    for task in tasks:
        marker = f"[PONDER_FORGE_RUN_ID={run_id}] [PONDER_FORGE_TASK_ID={task['task_id']}] [PONDER_FORGE_ROLE={task['role']}]"
        if task_kind(task) == "lane_coordinator":
            context = build_lane_context(run, profile, task, lane_child_tasks(store, run_id, task), retry=True)
            role = "orchestrator"
        else:
            context = build_child_context(run, profile, task, retry=True)
            role = "leaf"
        payload_tasks.append(
            {
                "goal": f"{marker} Retry orphaned task: {task['goal']}",
                "context": context,
                "role": role,
            }
        )
    return {"tasks": payload_tasks}


def _raw(row: dict) -> dict:
    try:
        return json.loads(row.get("raw_json") or "{}")
    except json.JSONDecodeError:
        return {}


def _merge_payloads(*payloads: dict) -> dict:
    tasks = []
    for payload in payloads:
        tasks.extend(payload.get("tasks") or [])
    return {"tasks": tasks}


def _gate_gap_repair_tasks(store: PonderForgeStore, run_id: str, run: dict, gate: dict) -> list[dict]:
    existing = _existing_gate_gap_tasks(store, run_id)
    by_assertion_id = {str(_raw(task).get("target_assertion_id")): task for task in existing}
    gaps_by_assertion = _assertion_gap_groups(store, run_id, gate)
    for assertion_id, gaps in gaps_by_assertion.items():
        if assertion_id in by_assertion_id:
            continue
        assertion = _assertion_by_id(store, run_id, assertion_id)
        if not assertion:
            continue
        context = _gate_gap_context(run, assertion, gaps)
        task = store.create_task(
            run_id,
            role="gate_gap_repairer",
            goal=f"Repair gate gaps for assertion {assertion_id}",
            context=context,
            parent_task_id=_producer_task_id(store, assertion),
            priority=20,
            raw={"reconcile_mode": "gate_gap_repair", "target_assertion_id": assertion_id, "gate_gap_types": [gap.get("gap_type") for gap in gaps]},
        )
        store.update_assertion_status(assertion_id, "needs_revision")
        by_assertion_id[assertion_id] = task
    return list(by_assertion_id.values())


def _existing_gate_gap_tasks(store: PonderForgeStore, run_id: str) -> list[dict]:
    tasks = []
    active_statuses = {"queued", "planned", "running", "orphan"}
    for task in store.list_rows("agent_tasks", run_id):
        raw = _raw(task)
        if raw.get("reconcile_mode") == "gate_gap_repair" and raw.get("target_assertion_id") and task.get("status") in active_statuses:
            tasks.append(task)
    return tasks


def _assertion_gap_groups(store: PonderForgeStore, run_id: str, gate: dict) -> dict[str, list[dict]]:
    assertion_ids = {row["assertion_id"] for row in store.list_rows("assertions", run_id)}
    grouped: dict[str, list[dict]] = {}
    for gap in gate.get("gaps") or []:
        target_id = str(gap.get("target_id") or "")
        if target_id in assertion_ids:
            grouped.setdefault(target_id, []).append(gap)
    return grouped


def _assertion_by_id(store: PonderForgeStore, run_id: str, assertion_id: str) -> dict | None:
    for assertion in store.list_rows("assertions", run_id):
        if assertion.get("assertion_id") == assertion_id:
            return assertion
    return None


def _producer_task_id(store: PonderForgeStore, assertion: dict) -> str | None:
    report_id = assertion.get("report_id")
    if not report_id:
        return None
    report = store.get_report(str(report_id))
    return str(report.get("task_id")) if report and report.get("task_id") else None


def _gate_gap_context(run: dict, assertion: dict, gaps: list[dict]) -> str:
    gap_lines = []
    for gap in gaps:
        gap_lines.append(
            "- "
            f"gap_type={gap.get('gap_type')}; "
            f"reason={gap.get('reason')}; "
            f"profile_specific_reason={gap.get('profile_specific_reason') or 'none'}; "
            f"required_groups={gap.get('required_groups') or 'none'}"
        )
    return "\n".join(
        [
            "Gate gap repair context:",
            f"run_id={run['run_id']}",
            f"profile={run['profile']}",
            f"target_assertion_id={assertion['assertion_id']}",
            "",
            "Original assertion requiring revision or stronger evidence:",
            f"- assertion_type: {assertion.get('assertion_type')}",
            f"- text: {assertion.get('text')}",
            f"- importance: {assertion.get('importance')}",
            "",
            "Gate gaps to repair:",
            *gap_lines,
            "",
            "Required output:",
            "- Return one JSON report suitable for `ponder-forge submit-report --file ...`.",
            "- Include this repair task_id as `task_id` in the report.",
            "- Revise/narrow unsupported assertions or add reviewer-visible evidence that directly resolves the listed gaps.",
            "- For analysis profile metric evidence, include metric_output evidence with `command` and `exit_code: 0` when claiming computed results.",
            "- Use `\"artifacts\": []` if there are no artifacts.",
            "- Do not edit the source quest; report only evidence from read-only inspection.",
        ]
    )


def _gate_gap_payload(run_id: str, run: dict, tasks: list[dict]) -> dict:
    payload_tasks = []
    for task in tasks:
        marker = f"[PONDER_FORGE_RUN_ID={run_id}] [PONDER_FORGE_TASK_ID={task['task_id']}] [PONDER_FORGE_ROLE={task['role']}]"
        payload_tasks.append(
            {
                "goal": f"{marker} {task['goal']}",
                "context": f"[PONDER_FORGE_PROFILE={run['profile']}]\nrepair_task_id={task['task_id']}\n{task['context']}",
                "role": "leaf",
            }
        )
    return {"tasks": payload_tasks}
