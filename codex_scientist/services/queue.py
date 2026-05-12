from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .project_state import ProjectLayout
from .runner import RunnerService

TERMINAL_STATUSES = {"completed", "failed_metric", "failed_artifact", "failed_readonly", "failed_timeout", "failed_other", "failed_oom", "failed_transient", "cancelled", "stuck"}
RETRYABLE_STATUSES = {"failed_oom", "failed_transient"}
ATTEMPTABLE_STATUSES = {"pending", "reconcile_required", "failed_oom", "failed_transient", "failed_other", "stuck", "cancelled"}


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
            payload = event.get("payload") or {}
            if event.get("event_type") == "queue.job_submitted":
                jobs[payload["job_id"]] = {
                    "job_id": payload["job_id"],
                    "command": payload.get("command"),
                    "status": "pending",
                    "attempts": 0,
                    "run_ids": [],
                    "expected_outputs": [],
                    "max_attempts": int(payload.get("max_attempts") or 3),
                    "retry_policy": payload.get("retry_policy") or "oom_or_transient",
                    "resource": payload.get("resource") or {},
                }
            if event.get("event_type") == "queue.job_attempt_started":
                job = jobs.setdefault(payload["job_id"], {"job_id": payload["job_id"]})
                job.update(
                    {
                        "status": "running",
                        "latest_run_id": payload.get("run_id"),
                        "worker_id": payload.get("worker_id"),
                        "attempts": payload.get("attempts", int(job.get("attempts") or 0) + 1),
                        "expected_outputs": payload.get("expected_outputs") or job.get("expected_outputs") or [],
                    }
                )
                run_ids = list(job.get("run_ids") or [])
                if payload.get("run_id") and payload.get("run_id") not in run_ids:
                    run_ids.append(payload.get("run_id"))
                job["run_ids"] = run_ids
            if event.get("event_type") == "queue.job_updated":
                job = jobs.setdefault(payload["job_id"], {"job_id": payload["job_id"]})
                job.update({key: value for key, value in payload.items() if key != "job_id"})
        return state

    def _quest_refs(self, quest_id: str | None, relative_path: str | Path) -> dict[str, str]:
        if not quest_id:
            return {}
        quest = self.layout.ensure_quest_layout(quest_id)
        detail_path = quest.detail_path(relative_path)
        return {"quest_id": quest.quest_id, "quest_root": str(quest.quest_root), "detail_path": str(detail_path)}

    def _write_job_detail(self, job: dict[str, Any]) -> None:
        detail_path = str(job.get("detail_path") or "").strip()
        if not detail_path:
            return
        path = Path(detail_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _decorate(job: dict[str, Any]) -> dict[str, Any]:
        decorated = dict(job)
        status = decorated.get("status")
        decorated["terminal"] = status in TERMINAL_STATUSES
        decorated["retryable"] = status in RETRYABLE_STATUSES
        decorated.setdefault("attempts", 0)
        decorated.setdefault("run_ids", [])
        decorated.setdefault("expected_outputs", [])
        decorated.setdefault("max_attempts", 3)
        decorated.setdefault("retry_policy", "oom_or_transient")
        decorated.setdefault("resource", {})
        return decorated

    def submit(self, *, job_id: str, command: str, max_attempts: int = 3, retry_policy: str = "oom_or_transient", resource: dict[str, Any] | None = None, quest_id: str | None = None) -> dict[str, Any]:
        state = self._read_snapshot()
        job = {
            "job_id": job_id,
            "command": command,
            "status": "pending",
            "created_at": _utc_now(),
            "attempts": 0,
            "run_ids": [],
            "expected_outputs": [],
            "max_attempts": max(1, int(max_attempts or 1)),
            "retry_policy": str(retry_policy or "oom_or_transient"),
            "resource": dict(resource or {}),
            **self._quest_refs(quest_id, Path("runtime") / "queue" / f"{job_id}.json"),
        }
        state["jobs"][job_id] = job
        self._write_job_detail(job)
        self._write_snapshot(state)
        self.events.append("queue.job_submitted", {"job_id": job_id, "command": command, "max_attempts": job["max_attempts"], "retry_policy": job["retry_policy"], "resource": job["resource"], "quest_id": job.get("quest_id"), "quest_root": job.get("quest_root"), "detail_path": job.get("detail_path")}, idempotency_key=f"queue.submit:{job_id}")
        return {"ok": True, "job": self._decorate(job)}

    def update_job(self, job_id: str, status: str, **fields: Any) -> dict[str, Any]:
        state = self._read_snapshot()
        job = state["jobs"].setdefault(job_id, {"job_id": job_id, "attempts": 0, "run_ids": [], "expected_outputs": []})
        job["status"] = status
        job.update(fields)
        job["updated_at"] = _utc_now()
        self._write_job_detail(job)
        self._write_snapshot(state)
        event_payload = {"job_id": job_id, "status": status, **fields}
        self.events.append("queue.job_updated", event_payload)
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

    def start_attempt(
        self,
        job_id: str,
        *,
        runner: RunnerService | None = None,
        worker_id: str | None = None,
        expected_outputs: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        state = self._read_snapshot()
        job = state.get("jobs", {}).get(job_id)
        if not job:
            return {"ok": False, "error": f"Unknown job: {job_id}", "error_type": "not_found", "recoverable": True}
        if job.get("status") not in ATTEMPTABLE_STATUSES:
            return {"ok": False, "error": f"Job is not attemptable: {job.get('status')}", "error_type": "not_attemptable", "recoverable": True}
        attempts = int(job.get("attempts") or 0)
        max_attempts = max(1, int(job.get("max_attempts") or 3))
        if attempts >= max_attempts:
            return {
                "ok": False,
                "error": f"Job reached max_attempts: {job_id}",
                "error_type": "max_attempts_exceeded",
                "recoverable": True,
                "job": self._decorate(job),
            }
        runner = runner or RunnerService(self.layout)
        started = runner.start(command=str(job.get("command") or ""), job_id=job_id, dry_run=dry_run, quest_id=job.get("quest_id"))
        run = started["run"]
        run_ids = list(job.get("run_ids") or [])
        run_ids.append(run["run_id"])
        job["run_ids"] = run_ids
        job["latest_run_id"] = run["run_id"]
        job["attempts"] = int(job.get("attempts") or 0) + 1
        job["status"] = "running"
        job["worker_id"] = worker_id
        if expected_outputs is not None:
            job["expected_outputs"] = list(expected_outputs)
        else:
            job.setdefault("expected_outputs", [])
        job["updated_at"] = _utc_now()
        self._write_job_detail(job)
        self._write_snapshot(state)
        self.events.append(
            "queue.job_attempt_started",
            {
                "job_id": job_id,
                "run_id": run["run_id"],
                "worker_id": worker_id,
                "attempts": job["attempts"],
                "expected_outputs": job.get("expected_outputs") or [],
            },
            idempotency_key=f"queue.attempt:{job_id}:{run['run_id']}",
        )
        return {"ok": True, "job": self._decorate(job), "run": run}

    def _expected_output_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.layout.project_root / path

    def _sync_running_job_from_runner(self, job_id: str, job: dict[str, Any], runner: RunnerService) -> bool:
        run_id = job.get("latest_run_id")
        if not run_id:
            return False
        try:
            run = runner.get(str(run_id))
        except FileNotFoundError:
            job["status"] = "reconcile_required"
            job["stuck_taxonomy"] = "missing_run_snapshot"
            return True
        if run.get("status") == "running" and not runner.is_process_alive(run.get("pid")):
            collected = runner.collect(str(run_id))
            run = collected.get("run", run)
        if run.get("status") not in TERMINAL_STATUSES:
            heartbeat_path = Path(run.get("heartbeat_path") or "")
            if not heartbeat_path.exists():
                job["status"] = "reconcile_required"
                job["stuck_taxonomy"] = "missing_heartbeat"
                return True
            return False
        expected_outputs = [self._expected_output_path(str(item)) for item in (job.get("expected_outputs") or [])]
        missing_outputs = [str(path) for path in expected_outputs if not path.exists()]
        if run.get("status") == "completed" and missing_outputs:
            job["status"] = "failed_artifact"
            job["stuck_taxonomy"] = "missing_expected_outputs"
            job["missing_expected_outputs"] = missing_outputs
        else:
            job["status"] = run.get("status")
            job.pop("missing_expected_outputs", None)
            job.pop("stuck_taxonomy", None)
        job["latest_run_id"] = run_id
        job["last_log_digest"] = runner.log_digest(str(run_id), max_tail_lines=20)
        job["updated_at"] = _utc_now()
        return True

    def reconcile_expired_leases(self) -> dict[str, Any]:
        state = self._read_snapshot()
        now = datetime.now(UTC)
        changed: list[str] = []
        runner = RunnerService(self.layout)
        for job_id, job in (state.get("jobs") or {}).items():
            if job.get("status") in {"leased", "running"}:
                expires_at = job.get("lease_expires_at")
                if expires_at and _parse_time(expires_at) <= now:
                    job["status"] = "reconcile_required"
                    job["stuck_taxonomy"] = "lease_expired"
                    job["updated_at"] = _utc_now()
                    changed.append(job_id)
                    self.events.append("queue.job_updated", {"job_id": job_id, "status": "reconcile_required", "stuck_taxonomy": "lease_expired"})
                    continue
            if job.get("status") == "running" and self._sync_running_job_from_runner(job_id, job, runner):
                changed.append(job_id)
                self.events.append("queue.job_updated", {"job_id": job_id, "status": job.get("status"), "latest_run_id": job.get("latest_run_id")})
        if changed:
            self._write_snapshot(state)
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self._read_snapshot()
        jobs = {job_id: self._decorate(job) for job_id, job in sorted((state.get("jobs") or {}).items())}
        all_done = bool(jobs) and all(job.get("terminal") for job in jobs.values())
        if not jobs:
            all_done_reason = "no_jobs"
        elif all_done:
            all_done_reason = "all_jobs_terminal"
        else:
            active = [job_id for job_id, job in jobs.items() if not job.get("terminal")]
            all_done_reason = "active_jobs:" + ",".join(active)
        return {"ok": True, "all_done": all_done, "all_done_reason": all_done_reason, "jobs": jobs, "path": str(self.state_path)}
