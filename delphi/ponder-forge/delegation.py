"""Prepare model-selected work for the host's native agent runtime."""
from __future__ import annotations
import json
import re

try:
    from .planner import plan_run, require_active_run, task_board
    from .strategy import worker_prompt
except ImportError:
    from planner import plan_run, require_active_run, task_board
    from strategy import worker_prompt

ATTACH = re.compile(r'<attach\s+agent=[\"\']([^\"\']+)[\"\']\s*/>')


def report_content(report: dict) -> str:
    raw = json.loads(report.get("raw_json") or "{}")
    return raw.get("content") or report["summary"]


def _attach_reports(store, run_id: str, prompt: str) -> str:
    tasks = {x["task_id"]: x for x in store.list_rows("agent_tasks", run_id)}
    latest = {}
    for report in store.list_rows("reports", run_id):
        task = tasks.get(report["task_id"])
        if task:
            name = json.loads(task["raw_json"] or "{}").get("agent", task["role"])
            latest[name] = report
    def replace(match):
        name = match.group(1)
        if name not in latest:
            raise ValueError(f"no returned report for attachment agent: {name}")
        return f"\n--- Full report from {name} ---\n{report_content(latest[name])}\n--- End report ---\n"
    return ATTACH.sub(replace, prompt)


def prepare_delegations(store, run_id: str, payload: dict | None = None, *, allocation_ids: list[str] | None = None) -> dict:
    run = require_active_run(store, run_id)
    # Old runs may retain retired topology settings; only the batch size is relevant now.
    limit = json.loads(run.get("budget_json") or "{}").get("delegate_batch_size", 20)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("invalid saved delegate_batch_size")
    selected = None
    if payload is not None:
        items = payload.get("tasks")
        if not isinstance(items, list) or not 1 <= len(items) <= limit:
            raise ValueError(f"assignments must contain 1 to {limit} tasks")
        if allocation_ids is not None and (len(allocation_ids) != len(items) or len(set(allocation_ids)) != len(items)):
            raise ValueError("allocation identities must match the assignment batch")
        board = {x["id"]: x for x in task_board(store, run_id)}
        normalized, names = [], set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("each assignment must be an object")
            name, prompt, role = item.get("agent"), item.get("prompt"), item.get("system_prompt", "")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("assignment requires an agent name")
            name = name.strip()
            if name in names:
                raise ValueError("assign one task per agent per batch; follow up serially")
            names.add(name)
            if not isinstance(prompt, str) or not prompt.strip() or not isinstance(role, str):
                raise ValueError("assignment requires prompt text and an optional system_prompt")
            ids = item.get("task_ids", [])
            if not isinstance(ids, list) or any(not isinstance(x, str) or x not in board for x in ids):
                raise ValueError("assignment task_ids must belong to this run's board")
            prompt = _attach_reports(store, run_id, prompt)
            normalized.append((name, prompt, role, list(dict.fromkeys(ids))))
        selected = []
        for index, (name, prompt, role, ids) in enumerate(normalized):
            task_id = allocation_ids[index] if allocation_ids else None
            task = store.get_task(task_id) if task_id else None
            raw = {"agent": name, "system_prompt": role, "task_ids": ids}
            if task and (task["run_id"] != run_id or json.loads(task["raw_json"] or "{}") != raw):
                raise ValueError("allocation identity belongs to a different assignment")
            task = task or store.create_task(run_id, name, prompt, context=worker_prompt(name, role)
                    + f"\n# Current assignment\nOriginal question: {run['user_goal']}\n"
                    + f"Constraints: {json.loads(run.get('config_json') or '{}').get('constraints', '')}\n",
                raw=raw, task_id=task_id)
            selected.append(task)
        # Bind logical owners; this does not claim execution or resolve a research question.
        updates = [{"id": tid, "owners": [name]} for name, _, _, ids in normalized for tid in ids]
        if updates:
            plan_run(store, run_id, {"tasks": updates})
    # Old lane/child records stay in history; do not dispatch their retired nested prompts.
    queued = [x for x in store.list_rows("agent_tasks", run_id)
              if x["status"] == "queued" and json.loads(x["raw_json"] or "{}").get("agent")]
    selected = selected if selected is not None else queued[:limit]
    assignments = []
    for task in selected:
        raw = json.loads(task["raw_json"] or "{}")
        name = raw.get("agent", task["role"])
        context = task["context"]
        assignments.append({"task_id": task["task_id"], "agent": name, "prompt": task["goal"],
                            "system_prompt": context, "task_ids": raw.get("task_ids", [])})
    return {"run_id": run_id, "assignments": assignments,
            "execution_owner": "native_host",
            "remaining_queued_tasks": max(0, len(queued) - len(selected)),
            "instruction": "Pass each assignment's full system_prompt and prompt together to the native host agent. "
                "On Hermes, map prompt to delegate_task goal and system_prompt to context. "
                "Reuse a host agent for serial follow-ups. Record actual launches with delegations --started, "
                "then collect full replies and submit-report. Preparation alone is not a launch receipt; "
                "do not redispatch a task already running on the host."}


def record_dispatch(store, run_id: str, task_id: str, *, host_agent_id: str | None = None,
                    cancelled: bool = False) -> dict:
    require_active_run(store, run_id)
    task = store.get_task(task_id)
    if not task or task["run_id"] != run_id:
        raise ValueError("assignment task_id does not belong to this run")
    if cancelled:
        if task["status"] not in {"queued", "running", "cancelled"}:
            raise ValueError("cannot cancel a returned assignment")
        store.update_task_status(task_id, "cancelled")
    else:
        if not json.loads(task["raw_json"] or "{}").get("agent"):
            raise ValueError("legacy assignment cannot be relaunched; create a new scoped assignment")
        if not host_agent_id or not host_agent_id.strip():
            raise ValueError("recording a launch requires --host-agent-id")
        if task["status"] not in {"queued", "running"}:
            raise ValueError("cannot launch a returned assignment")
        existing = task.get("hermes_subagent_id")
        if existing and existing != host_agent_id:
            raise ValueError("assignment already bound to a different host agent")
        store.update_task_binding(task_id, subagent_id=host_agent_id)
    recorded = store.get_task(task_id)
    return {"run_id": run_id, "task_id": task_id, "agent": recorded["role"],
            "status": recorded["status"], "host_agent_id": recorded["hermes_subagent_id"]}
