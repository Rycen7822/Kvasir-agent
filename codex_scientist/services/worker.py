from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .feedback_ingest import FeedbackIngestService
from .project_state import ProjectLayout
from .queue import QueueService
from .runner import RunnerService
from .scheduler import SchedulerService, _error
from .trajectory import TrajectoryStore


class WorkerService:
    """Local worker protocol for execution-grounded scheduler jobs."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.queue = QueueService(layout)
        self.runner = RunnerService(layout)

    def claim(
        self,
        *,
        worker_id: str,
        ttl_seconds: int = 3600,
        dry_run: bool = False,
        quest_id: str | None = None,
        env_id: str | None = None,
    ) -> dict[str, Any]:
        leased = self.queue.lease_next(worker_id=worker_id, ttl_seconds=ttl_seconds, quest_id=quest_id, env_id=env_id)
        if leased.get("ok") is not True:
            return leased
        job = leased["job"]
        scoped = self._verify_scope(job, quest_id=quest_id, env_id=env_id)
        if scoped.get("ok") is not True:
            self.queue.update_job(str(job["job_id"]), "failed_readonly", stuck_taxonomy=scoped.get("error_type"), failure=scoped)
            return scoped
        verified = self._verify_job(job)
        if verified.get("ok") is not True:
            self.queue.update_job(str(job["job_id"]), "failed_readonly", stuck_taxonomy=verified.get("error_type"), failure=verified)
            return verified
        started = self.queue.start_attempt(
            str(job["job_id"]),
            runner=self.runner,
            worker_id=worker_id,
            expected_outputs=list(job.get("expected_outputs") or []),
            dry_run=dry_run,
        )
        return started

    def heartbeat(self, *, run_id: str, quest_id: str | None = None, env_id: str | None = None) -> dict[str, Any]:
        job = self._job_for_run(run_id)
        if job is None:
            return _error("not_found", f"Unknown run: {run_id}", recoverable=True)
        scoped = self._verify_scope(job, quest_id=quest_id, env_id=env_id)
        if scoped.get("ok") is not True:
            return scoped
        return self.runner.heartbeat(run_id)

    def upload_artifact(self, *, job_id: str, artifact_path: str, kind: str = "artifact", quest_id: str | None = None, env_id: str | None = None) -> dict[str, Any]:
        status = self.queue.status()
        job = (status.get("jobs") or {}).get(job_id)
        if not isinstance(job, dict):
            return _error("not_found", f"Unknown job: {job_id}", recoverable=True)
        scoped = self._verify_scope(job, quest_id=quest_id, env_id=env_id)
        if scoped.get("ok") is not True:
            return scoped
        source = Path(artifact_path).expanduser().resolve()
        if not source.is_file():
            return _error("invalid_path", f"artifact_path does not exist: {artifact_path}", recoverable=True)
        raw_resource = job.get("resource")
        resource = raw_resource if isinstance(raw_resource, dict) else {}
        quest_id = str(resource.get("quest_id") or job.get("quest_id") or "").strip()
        if not quest_id:
            return _error("invalid_scheduler_job", "Scheduler job has no quest_id for artifact upload", recoverable=True)
        run_id = str(job.get("latest_run_id") or "unclaimed")
        safe_kind = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(kind or "artifact"))[:80] or "artifact"
        safe_name = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in source.name)[:120] or "artifact.bin"
        quest = self.layout.ensure_quest_layout(quest_id)
        destination_dir = quest.detail_path(Path("artifacts") / "execution_grounded" / run_id / "uploads")
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{safe_kind}_{safe_name}"
        shutil.copy2(source, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        artifact_ref = {"path": str(destination), "sha256": digest, "kind": safe_kind, "job_id": job_id, "run_id": run_id}
        self.queue.update_job(job_id, str(job.get("status") or "running"), uploaded_artifacts=[*(job.get("uploaded_artifacts") or []), artifact_ref])
        return {"ok": True, "artifact_ref": artifact_ref}

    def collect(self, *, job_id: str, trusted_primary_metric: bool = False, quest_id: str | None = None, env_id: str | None = None) -> dict[str, Any]:
        status = self.queue.status()
        job = (status.get("jobs") or {}).get(job_id)
        if not isinstance(job, dict):
            return _error("not_found", f"Unknown job: {job_id}", recoverable=True)
        scoped = self._verify_scope(job, quest_id=quest_id, env_id=env_id)
        if scoped.get("ok") is not True:
            return scoped
        run_id = str(job.get("latest_run_id") or "")
        if not run_id:
            return _error("missing_run", f"Job has no run to collect: {job_id}", recoverable=True, job=job)
        collected = self.runner.collect(run_id)
        raw_run = collected.get("run")
        run = raw_run if isinstance(raw_run, dict) else {}
        if collected.get("collected") is not True:
            return {"ok": True, "collected": False, "job": job, "run": run}
        raw_resource = job.get("resource")
        resource = raw_resource if isinstance(raw_resource, dict) else {}
        trajectory_id = str(resource.get("trajectory_id") or "")
        quest_id = str(resource.get("quest_id") or job.get("quest_id") or "")
        env_id = str(resource.get("env_id") or "")
        run_status = str(run.get("status") or "")
        if run_status != "completed":
            failure_class = self._failure_class(run_id=run_id)
            updated = self.queue.update_job(job_id, self._job_status_for_failure(failure_class), latest_run_id=run_id, failure_class=failure_class)
            if quest_id and trajectory_id:
                TrajectoryStore(self.layout).update_result(quest_id=quest_id, trajectory_id=trajectory_id, result={"status": "failed"}, failure={"class": failure_class, "message": f"runner status: {run_status}"})
            return {"ok": False, "error_type": failure_class, "error": f"Worker run failed: {run_status}", "recoverable": True, "collected": True, "job": updated["job"], "run": run}
        metrics_path = self._first_existing_output(job)
        if metrics_path is None:
            updated = self.queue.update_job(job_id, "failed_metric", latest_run_id=run_id, failure_class="metric_missing")
            if quest_id and trajectory_id:
                TrajectoryStore(self.layout).update_result(quest_id=quest_id, trajectory_id=trajectory_id, result={"status": "failed"}, failure={"class": "metric_missing", "message": "expected metrics output missing"})
            return {"ok": False, "error_type": "metric_missing", "error": "Expected metrics output missing", "recoverable": True, "collected": True, "job": updated["job"], "run": run}
        feedback = FeedbackIngestService(self.layout).ingest(
            quest_id=quest_id,
            env_id=env_id,
            trajectory_id=trajectory_id,
            run_id=run_id,
            source_kind="local_metrics",
            metrics_path=str(metrics_path),
            log_paths=[str(run.get("log_path"))] if run.get("log_path") else [],
            trusted_primary_metric=trusted_primary_metric,
        )
        if feedback.get("ok") is not True:
            updated = self.queue.update_job(job_id, "failed_metric", latest_run_id=run_id, failure_class=feedback.get("error_type"))
            feedback.update({"collected": True, "job": updated["job"], "run": run})
            return feedback
        raw_feedback_payload = feedback.get("feedback")
        feedback_payload = raw_feedback_payload if isinstance(raw_feedback_payload, dict) else {}
        if feedback_payload.get("status") != "parsed":
            error_type = str(feedback_payload.get("status") or "metric_invalid")
            updated = self.queue.update_job(job_id, "failed_metric", latest_run_id=run_id, feedback_path=feedback.get("path"), failure_class=error_type)
            return {
                "ok": False,
                "error_type": error_type,
                "error": "Worker feedback did not contain a parsed primary metric",
                "recoverable": True,
                "collected": True,
                "job": updated["job"],
                "run": run,
                "feedback": feedback_payload,
            }
        updated = self.queue.update_job(job_id, "completed", latest_run_id=run_id, feedback_path=feedback.get("path"))
        return {"ok": True, "collected": True, "job": updated["job"], "run": run, "feedback": feedback_payload}

    def _verify_scope(self, job: dict[str, Any], *, quest_id: str | None = None, env_id: str | None = None) -> dict[str, Any]:
        raw_resource = job.get("resource")
        resource = raw_resource if isinstance(raw_resource, dict) else {}
        actual_quest_id = str(resource.get("quest_id") or job.get("quest_id") or "")
        actual_env_id = str(resource.get("env_id") or "")
        if quest_id is not None and actual_quest_id != str(quest_id):
            return _error("scope_mismatch", "Worker job quest_id does not match requested executor scope", recoverable=False, expected_quest_id=str(quest_id), actual_quest_id=actual_quest_id)
        if env_id is not None and actual_env_id != str(env_id):
            return _error("scope_mismatch", "Worker job env_id does not match requested executor scope", recoverable=False, expected_env_id=str(env_id), actual_env_id=actual_env_id)
        return {"ok": True}

    def _job_for_run(self, run_id: str) -> dict[str, Any] | None:
        jobs = self.queue.status().get("jobs") or {}
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            if str(job.get("latest_run_id") or "") == str(run_id):
                return job
            if str(run_id) in {str(item) for item in (job.get("run_ids") or [])}:
                return job
        return None

    def _verify_job(self, job: dict[str, Any]) -> dict[str, Any]:
        resource = job.get("resource") if isinstance(job.get("resource"), dict) else {}
        required = ["quest_id", "env_id", "trajectory_id", "variant_id", "package_path"]
        missing = [key for key in required if not str(resource.get(key) or "").strip()]
        if missing:
            return _error("invalid_scheduler_job", "Scheduler job is missing execution-grounded resource fields", missing=missing)
        return SchedulerService(self.layout).validate_package(
            quest_id=str(resource["quest_id"]),
            env_id=str(resource["env_id"]),
            trajectory_id=str(resource["trajectory_id"]),
            variant_id=str(resource["variant_id"]),
            package_path=str(resource["package_path"]),
        )

    def _first_existing_output(self, job: dict[str, Any]) -> Path | None:
        for item in job.get("expected_outputs") or []:
            path = Path(str(item)).expanduser()
            if not path.is_absolute():
                path = self.layout.project_root / path
            if path.is_file():
                return path
        return None

    def _failure_class(self, *, run_id: str) -> str:
        digest = self.runner.log_digest(run_id, max_tail_lines=40)
        if digest.get("top_error_class") == "oom":
            return "oom"
        return "runtime_exception" if digest.get("top_error_class") in {"exception", "error"} else "runtime_exception"

    @staticmethod
    def _job_status_for_failure(failure_class: str) -> str:
        if failure_class == "oom":
            return "failed_oom"
        return "failed_other"
