from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .environment import EnvironmentService
from .event_store import EventStore
from .project_state import ProjectLayout, _safe_segment
from .queue import QueueService

_NONLOCAL_BACKENDS = {"slurm", "k8s", "ray", "cloud"}


def _error(error_type: str, message: str, *, recoverable: bool = True, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error_type": error_type, "error": message, "recoverable": recoverable}
    payload.update(extra)
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("package manifest must be a JSON object")
    return loaded


class SchedulerService:
    """Executor scheduler abstraction.

    The current concrete backend is local-only and delegates to QueueService/RunnerService. Other backends are explicit manifest-only stubs until connector-specific tests exist.
    """

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def submit(
        self,
        *,
        quest_id: str,
        env_id: str,
        trajectory_id: str,
        variant_id: str,
        package_path: str,
        backend: str = "local",
        command: str | None = None,
        expected_outputs: list[str] | None = None,
        max_attempts: int = 1,
    ) -> dict[str, Any]:
        try:
            safe_quest_id = _safe_segment(quest_id, label="quest_id")
            safe_env_id = _safe_segment(env_id, label="env_id")
            safe_trajectory_id = _safe_segment(trajectory_id, label="trajectory_id")
            safe_variant_id = _safe_segment(variant_id, label="variant_id")
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        backend_name = str(backend or "local").strip().lower() or "local"
        if backend_name in _NONLOCAL_BACKENDS:
            return _error("backend_not_implemented", f"Scheduler backend is not implemented yet: {backend_name}", backend=backend_name)
        if backend_name != "local":
            return _error("invalid_backend", f"Unsupported scheduler backend: {backend_name}", backend=backend_name)
        if not str(command or "").strip():
            return _error("missing_argument", "local scheduler backend requires command", recoverable=True)

        validation = self._validate_submission(
            quest_id=safe_quest_id,
            env_id=safe_env_id,
            trajectory_id=safe_trajectory_id,
            variant_id=safe_variant_id,
            package_path=package_path,
        )
        if validation.get("ok") is not True:
            return validation
        package = validation["package"]
        outputs = [str(item) for item in (expected_outputs or [])]
        job_id = f"job_{safe_variant_id}"
        resource = {
            "backend": backend_name,
            "quest_id": safe_quest_id,
            "env_id": safe_env_id,
            "trajectory_id": safe_trajectory_id,
            "variant_id": safe_variant_id,
            "package_path": str(validation["package_path"]),
            "archive_path": str(package.get("archive_path") or ""),
            "archive_sha256": str(package.get("archive_sha256") or ""),
            "source": "execution_grounded_scheduler",
        }
        queue = QueueService(self.layout)
        submitted = queue.submit(job_id=job_id, command=str(command), max_attempts=max_attempts, retry_policy="executor_terminal", resource=resource, quest_id=safe_quest_id)
        job = submitted["job"]
        if outputs:
            updated = queue.update_job(job_id, "pending", expected_outputs=outputs, resource=resource)
            job = updated["job"]
        self.events.append("scheduler.submitted", {"quest_id": safe_quest_id, "env_id": safe_env_id, "variant_id": safe_variant_id, "job_id": job_id, "backend": backend_name}, idempotency_key=f"scheduler.submit:{safe_quest_id}:{safe_variant_id}")
        return {"ok": True, "job": job, "backend": backend_name, "package": {"path": str(validation["package_path"]), "archive_sha256": resource["archive_sha256"]}}

    def status(self) -> dict[str, Any]:
        return QueueService(self.layout).status()

    def validate_package(self, *, quest_id: str, env_id: str, trajectory_id: str, variant_id: str, package_path: str) -> dict[str, Any]:
        return self._validate_submission(quest_id=quest_id, env_id=env_id, trajectory_id=trajectory_id, variant_id=variant_id, package_path=package_path)

    def _validate_submission(self, *, quest_id: str, env_id: str, trajectory_id: str, variant_id: str, package_path: str) -> dict[str, Any]:
        env_service = EnvironmentService(self.layout)
        env_validation = env_service.validate(quest_id=quest_id, env_id=env_id)
        if env_validation.get("ok") is not True:
            return env_validation
        protected = env_service.protected_hash_report(quest_id=quest_id, env_id=env_id)
        if protected.get("ok") is not True:
            return protected
        path = Path(package_path).expanduser().resolve()
        if not path.is_file():
            return _error("invalid_path", f"package_path does not exist: {package_path}", recoverable=True)
        try:
            package = _read_json(path)
        except (json.JSONDecodeError, ValueError) as exc:
            return _error("invalid_schema", str(exc), recoverable=True)
        expected = {"quest_id": quest_id, "env_id": env_id, "trajectory_id": trajectory_id, "variant_id": variant_id}
        mismatches = {key: {"expected": value, "actual": package.get(key)} for key, value in expected.items() if str(package.get(key) or "") != value}
        if mismatches:
            return _error("package_mismatch", "Package manifest does not match scheduler request", recoverable=True, mismatches=mismatches)
        archive = Path(str(package.get("archive_path") or "")).expanduser().resolve()
        if not archive.is_file():
            return _error("invalid_path", f"package archive does not exist: {archive}", recoverable=True)
        actual_sha = _sha256(archive)
        expected_sha = str(package.get("archive_sha256") or "").strip()
        if actual_sha != expected_sha:
            return _error("package_hash_mismatch", "Package archive sha256 mismatch", recoverable=False, expected_sha256=expected_sha, actual_sha256=actual_sha)
        return {"ok": True, "package": package, "package_path": path, "protected_hash_report": protected}
