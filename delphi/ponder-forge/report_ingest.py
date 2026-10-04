"""Retain complete worker replies without imposing a scientific claim schema."""
from __future__ import annotations
import json
import math

try:
    from .planner import require_active_run
    from .delegation import report_content
except ImportError:
    from planner import require_active_run
    from delegation import report_content


def ingest_report(store, payload: dict) -> dict:
    run_id, task_id = payload.get("run_id"), payload.get("task_id")
    require_active_run(store, run_id)
    task = store.get_task(task_id) if isinstance(task_id, str) else None
    if not task or task["run_id"] != run_id:
        raise ValueError("report task_id does not belong to this run")
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("report requires the full content text")
    status = payload.get("status", "finished")
    if status not in {"finished", "partial", "failed", "cancelled"}:
        raise ValueError("report status must be finished, partial, failed or cancelled")
    confidence = payload.get("confidence")
    if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        raise ValueError("confidence must be between 0 and 1")
    report_id = payload.get("report_id")
    if report_id is not None and (not isinstance(report_id, str) or not report_id.strip()):
        raise ValueError("report_id must be a nonempty string")
    existing = store.get_report(report_id) if report_id else None
    if existing and (existing["run_id"] != run_id or existing["task_id"] != task_id
                     or report_content(existing) != content
                     or json.loads(existing["raw_json"] or "{}").get("status", "finished") != status):
        raise ValueError("report_id already belongs to different content or work")
    matches = [x for x in store.list_reports_for_task(task_id) if report_content(x) == content
               and json.loads(x["raw_json"] or "{}").get("status", "finished") == status]
    if existing or matches:
        return {"run_id": run_id, "report_id": (existing or matches[0])["report_id"], "idempotent": True}
    title = payload.get("title")
    if title is not None and not isinstance(title, str):
        raise ValueError("report title must be text")
    report = store.create_report(run_id=run_id, task_id=task_id, role=task["role"],
        title=title or task["goal"][:120], summary=content, confidence=confidence,
        raw={**payload, "status": status}, report_id=report_id)
    store.update_task_status(task_id, status)
    return {"run_id": run_id, "report_id": report["report_id"], "task_id": task_id, "status": status}
