from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from codex_scientist.runtime.redaction import redact_text

from .environment import EnvironmentService
from .event_store import EventStore
from .metric import extract_metric_value
from .project_state import ProjectLayout, _safe_segment
from .runner import RunnerService
from .trajectory import TrajectoryStore

_SOURCE_KINDS = {"local_metrics", "local_log", "wandb", "mlflow", "slurm", "k8s", "manual"}
_UNTRUSTED_BY_DEFAULT = {"wandb", "mlflow", "local_log", "manual"}


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
        raise ValueError("metrics payload must be a JSON object")
    return loaded


class FeedbackIngestService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def ingest(
        self,
        *,
        quest_id: str,
        env_id: str,
        trajectory_id: str,
        run_id: str,
        source_kind: str,
        metrics_path: str | None = None,
        log_paths: list[str] | None = None,
        trusted_primary_metric: bool = False,
    ) -> dict[str, Any]:
        try:
            safe_run_id = _safe_segment(run_id, label="run_id")
            safe_source_kind = _safe_segment(source_kind, label="source_kind")
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        if safe_source_kind not in _SOURCE_KINDS:
            return _error("invalid_source_kind", f"Unsupported feedback source_kind: {source_kind}", recoverable=True)

        env_validation = EnvironmentService(self.layout).validate(quest_id=quest_id, env_id=env_id)
        if env_validation.get("ok") is not True:
            return env_validation
        env_payload = EnvironmentService(self.layout).show(quest_id=quest_id, env_id=env_id)
        if env_payload.get("ok") is not True:
            return env_payload
        environment = env_payload["environment"]

        trajectory = TrajectoryStore(self.layout).show(quest_id=quest_id, trajectory_id=trajectory_id)
        if trajectory.get("ok") is not True:
            return trajectory

        quest = self.layout.ensure_quest_layout(quest_id)
        artifact_dir = quest.detail_path(Path("artifacts") / "execution_grounded" / safe_run_id)
        logs_dir = artifact_dir / "logs"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        copied_metrics_path: Path | None = None
        metrics_payload: dict[str, Any] | None = None
        if metrics_path:
            source_metrics = Path(metrics_path).expanduser().resolve()
            if not source_metrics.exists() or not source_metrics.is_file():
                return _error("invalid_path", f"metrics_path does not exist: {metrics_path}", recoverable=True)
            copied_metrics_path = artifact_dir / "metrics.json"
            shutil.copy2(source_metrics, copied_metrics_path)
            try:
                metrics_payload = _read_json(copied_metrics_path)
            except (json.JSONDecodeError, ValueError) as exc:
                metrics_payload = None
                metric_result = {"ok": False, "error_type": "metric_invalid", "error": str(exc)}
            else:
                metric_result = extract_metric_value(metrics_payload, environment["primary_metric"])
        else:
            metric_result = {"ok": False, "error_type": "metric_missing", "error": "metrics_path is required for primary metric extraction"}

        copied_logs = self._copy_logs(log_paths or [], logs_dir)
        log_digest = self._log_digest(run_id=safe_run_id, copied_logs=copied_logs)

        external_untrusted = safe_source_kind in _UNTRUSTED_BY_DEFAULT
        metric_ok = metric_result.get("ok") is True
        trusted = bool(trusted_primary_metric) and not external_untrusted and metric_ok
        requires_revalidation = not trusted

        if metric_result.get("ok") is True:
            feedback_status = "parsed"
            primary_metric = {
                "name": environment["primary_metric"].get("name"),
                "value": metric_result["value"],
                "direction": environment["primary_metric"].get("direction"),
            }
            trajectory_status = "evaluated" if trusted else "needs_revalidation"
            failure = None
        else:
            error_type = str(metric_result.get("error_type") or "metric_invalid")
            feedback_status = "metric_missing" if error_type == "metric_missing" else "metric_invalid"
            primary_metric = None
            trajectory_status = "metric_invalid"
            failure = {"class": "metric_missing" if error_type == "metric_missing" else "metric_invalid", "message": str(metric_result.get("error") or error_type)}

        feedback = {
            "schema_version": 1,
            "run_id": safe_run_id,
            "quest_id": quest_id,
            "env_id": env_id,
            "variant_id": (trajectory.get("trajectory") or {}).get("variant", {}).get("variant_id"),
            "trajectory_id": trajectory_id,
            "source_kind": safe_source_kind,
            "metrics_path": str(copied_metrics_path) if copied_metrics_path else None,
            "metrics_sha256": _sha256(copied_metrics_path) if copied_metrics_path else None,
            "log_paths": [str(item["path"]) for item in copied_logs],
            "primary_metric": primary_metric,
            "secondary_metrics": {},
            "parser": {"kind": environment["primary_metric"].get("parser"), "version": 1},
            "log_digest": log_digest,
            "status": feedback_status,
            "trusted_primary_metric": trusted,
            "requires_revalidation": requires_revalidation,
        }
        bundle_path = artifact_dir / "feedback_bundle.json"
        self.events.write_snapshot(feedback, path=bundle_path)

        TrajectoryStore(self.layout).update_result(
            quest_id=quest_id,
            trajectory_id=trajectory_id,
            result={
                "status": trajectory_status,
                "primary_metric": primary_metric,
                "trusted_primary_metric": trusted,
                "requires_revalidation": requires_revalidation,
            },
            failure=failure,
        )
        self.events.append("feedback.ingested", {"quest_id": quest_id, "env_id": env_id, "trajectory_id": trajectory_id, "run_id": safe_run_id, "status": feedback_status})
        hook_result: dict[str, Any] | None = None
        try:
            from .execution_hooks import ExecutionHooksService

            hook_result = ExecutionHooksService(self.layout).on_feedback_ingested(
                quest_id=quest_id,
                env_id=env_id,
                trajectory_id=trajectory_id,
                feedback=feedback,
                feedback_path=str(bundle_path),
            )
        except Exception as exc:
            hook_result = {"ok": False, "error_type": "hook_failed", "error": str(exc), "recoverable": True}
            self.events.append("hook.failed", {"quest_id": quest_id, "env_id": env_id, "trajectory_id": trajectory_id, "hook": "feedback_ingested", "error_type": "hook_failed"})
        return {"ok": True, "feedback": feedback, "path": str(bundle_path), "hook": hook_result}

    def _copy_logs(self, log_paths: list[str], logs_dir: Path) -> list[dict[str, Any]]:
        copied: list[dict[str, Any]] = []
        for raw in log_paths:
            source = Path(raw).expanduser().resolve()
            if not source.exists() or not source.is_file():
                continue
            name = _safe_segment(source.name, label="log_name")
            target = logs_dir / name
            if target.exists():
                target = logs_dir / f"{target.stem}_{len(copied)}{target.suffix}"
            shutil.copy2(source, target)
            copied.append({"path": target, "sha256": _sha256(target), "bytes": target.stat().st_size})
        return copied

    def _log_digest(self, *, run_id: str, copied_logs: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            runner_digest = RunnerService(self.layout).log_digest(run_id, max_tail_lines=40)
        except Exception:
            runner_digest = None
        if runner_digest and runner_digest.get("ok") is True:
            return runner_digest

        combined_text = ""
        items: list[dict[str, Any]] = []
        for item in copied_logs:
            path = Path(item["path"])
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            combined_text += "\n" + text
            lines = text.splitlines()
            items.append(
                {
                    "path": str(path),
                    "sha256": item["sha256"],
                    "bytes": item["bytes"],
                    "line_count": len(lines),
                    "tail": [redact_text(line) for line in lines[-20:]],
                }
            )
        lower = combined_text.lower()
        if "out of memory" in lower or "cuda oom" in lower:
            error_class = "oom"
        elif "traceback" in lower or "exception" in lower:
            error_class = "exception"
        elif "error" in lower or "failed" in lower:
            error_class = "error"
        else:
            error_class = "none"
        return {"ok": True, "run_id": run_id, "logs": items, "top_error_class": error_class}
