from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .project_state import ProjectLayout

TERMINAL_STATUSES = {"completed", "failed_metric", "failed_artifact", "failed_readonly", "failed_timeout", "failed_other", "cancelled", "stuck"}
RETRYABLE_STATUSES = {"failed_oom", "failed_transient"}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


class QueueService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.queue_dir = layout.state_root / "queue"
        self.state_path = self.queue_dir / "queue_state.json"

    def _empty_state(self) -> dict[str, Any]:
        return {"schema_version": 1, "updated_at": _utc_now(), "jobs": {}}

    def _read_snapshot(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._replay_state()
        loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else self._empty_state()

    def _write_snapshot(self, state: dict[str, Any]) -> None:
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = _utc_now()
        tmp = self.state_path.with_name(f"{self.state_path.name}.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.state_path)

    def _replay_state(self) -> dict[str, Any]:
        state = self._empty_state()
        jobs = state["jobs"]
        for event in self.events.read_events():
            if event.get("event_type") == "queue.job_submitted":
                payload = event.get("payload") or {}
                jobs[payload["job_id"]] = {"job_id": payload["job_id"], "command": payload.get("command"), "status": "pending"}
            if event.get("event_type") == "queue.job_updated":
                payload = event.get("payload") or {}
                job = jobs.setdefault(payload["job_id"], {"job_id": payload["job_id"]})
                job["status"] = payload.get("status")
        return state

    @staticmethod
    def _decorate(job: dict[str, Any]) -> dict[str, Any]:
        decorated = dict(job)
        status = decorated.get("status")
        decorated["terminal"] = status in TERMINAL_STATUSES
        decorated["retryable"] = status in RETRYABLE_STATUSES
        return decorated

    def submit(self, *, job_id: str, command: str) -> dict[str, Any]:
        state = self._read_snapshot()
        job = {"job_id": job_id, "command": command, "status": "pending", "created_at": _utc_now()}
        state["jobs"][job_id] = job
        self._write_snapshot(state)
        self.events.append("queue.job_submitted", {"job_id": job_id, "command": command})
        return {"ok": True, "job": self._decorate(job)}

    def update_job(self, job_id: str, status: str) -> dict[str, Any]:
        state = self._read_snapshot()
        job = state["jobs"].setdefault(job_id, {"job_id": job_id})
        job["status"] = status
        job["updated_at"] = _utc_now()
        self._write_snapshot(state)
        self.events.append("queue.job_updated", {"job_id": job_id, "status": status})
        return {"ok": True, "job": self._decorate(job)}

    def lease_next(self, *, worker_id: str, ttl_seconds: int) -> dict[str, Any]:
        state = self._read_snapshot()
        now = datetime.now(UTC)
        for job_id, job in sorted(state.get("jobs", {}).items()):
            if job.get("status") != "pending":
                continue
            job["status"] = "leased"
            job["worker_id"] = worker_id
            job["lease_expires_at"] = (now + timedelta(seconds=ttl_seconds)).replace(microsecond=0).isoformat()
            job["updated_at"] = _utc_now()
            self._write_snapshot(state)
            self.events.append("queue.job_leased", {"job_id": job_id, "worker_id": worker_id, "ttl_seconds": ttl_seconds})
            return {"ok": True, "job": self._decorate(job)}
        return {"ok": False, "error": "No pending jobs", "error_type": "empty_queue", "recoverable": True}

    def reconcile_expired_leases(self) -> dict[str, Any]:
        state = self._read_snapshot()
        now = datetime.now(UTC)
        changed: list[str] = []
        for job_id, job in (state.get("jobs") or {}).items():
            if job.get("status") not in {"leased", "running"}:
                continue
            expires_at = job.get("lease_expires_at")
            if expires_at and _parse_time(expires_at) <= now:
                job["status"] = "reconcile_required"
                job["updated_at"] = _utc_now()
                changed.append(job_id)
                self.events.append("queue.job_updated", {"job_id": job_id, "status": "reconcile_required"})
        if changed:
            self._write_snapshot(state)
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self._read_snapshot()
        jobs = {job_id: self._decorate(job) for job_id, job in sorted((state.get("jobs") or {}).items())}
        all_done = bool(jobs) and all(job.get("terminal") for job in jobs.values())
        return {"ok": True, "all_done": all_done, "jobs": jobs, "path": str(self.state_path)}
