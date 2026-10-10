"""Retain complete worker replies without imposing a scientific claim schema."""
from __future__ import annotations
import json
import math

try:
    from .store import json_dumps, new_id, now_iso
    from .delegation import report_content
except ImportError:
    from store import json_dumps, new_id, now_iso
    from delegation import report_content


def ingest_report(store, payload: dict) -> dict:
    run_id, task_id = payload.get("run_id"), payload.get("task_id")
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
    title = payload.get("title")
    if title is not None and not isinstance(title, str):
        raise ValueError("report title must be text")
    event = None
    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute("select * from runs where run_id = ?", (run_id,)).fetchone()
        if not run:
            raise ValueError(f"unknown run_id: {run_id}")
        if run["status"] in {"completed", "partial"}:
            raise ValueError("run is closed; start a new run for follow-up work")
        task = conn.execute("select * from agent_tasks where task_id = ?", (task_id,)).fetchone() if isinstance(task_id, str) else None
        if not task or task["run_id"] != run_id:
            raise ValueError("report task_id does not belong to this run")
        existing = conn.execute("select * from reports where report_id = ?", (report_id,)).fetchone() if report_id else None
        if existing and (existing["run_id"] != run_id or existing["task_id"] != task_id
                         or report_content(dict(existing)) != content
                         or json.loads(existing["raw_json"] or "{}").get("status", "finished") != status):
            raise ValueError("report_id already belongs to different content or work")
        # Older callers have no report ID. Keep their retry behavior scoped to this task.
        if not report_id:
            existing = next((row for row in conn.execute("select * from reports where task_id = ? order by rowid desc", (task_id,))
                if report_content(dict(row)) == content
                and json.loads(row["raw_json"] or "{}").get("status", "finished") == status), None)
        if existing:
            report_id = existing["report_id"]
            # Repair records saved by the former split transaction. An old report
            # must never overwrite a newer terminal task result.
            if task["status"] in {"queued", "running"}:
                conn.execute("update agent_tasks set status = ?, error = NULL, finished_at = ? where task_id = ?",
                             (status, now_iso(), task_id))
            result = {"run_id": run_id, "report_id": report_id, "task_id": task_id, "idempotent": True}
        else:
            report_id = report_id or new_id("report")
            saved_title = title or task["goal"][:120]
            timestamp = now_iso()
            conn.execute(
                """insert into reports(report_id, run_id, task_id, role, title, summary,
                   confidence, status, created_at, raw_json) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (report_id, run_id, task_id, task["role"], saved_title, content, confidence,
                 "submitted", timestamp, json_dumps({**payload, "status": status})),
            )
            event = {"event_id": new_id("event"), "run_id": run_id, "task_id": task_id,
                "session_id": None, "event_type": "report_created", "actor": "system",
                "payload_json": json_dumps({"role": task["role"], "title": saved_title, "report_id": report_id}),
                "created_at": timestamp}
            conn.execute(
                """insert into events(event_id, run_id, task_id, session_id, event_type, actor, payload_json, created_at)
                   values (?, ?, ?, ?, ?, ?, ?, ?)""", tuple(event.values()),
            )
            conn.execute("update agent_tasks set status = ?, error = NULL, finished_at = ? where task_id = ?",
                         (status, timestamp, task_id))
            result = {"run_id": run_id, "report_id": report_id, "task_id": task_id}
        result["status"] = conn.execute("select status from agent_tasks where task_id = ?", (task_id,)).fetchone()[0]
    if event:
        try:
            store._append_jsonl(run_id, {**event, "payload": json.loads(event["payload_json"])})
        except OSError as exc:
            # SQLite remains authoritative; a projection failure must not undo delivery.
            result["event_log_warning"] = str(exc)
    return result
