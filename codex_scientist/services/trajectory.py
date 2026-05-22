from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from .environment import EnvironmentService
from .event_store import EventStore, utc_now
from .project_state import ProjectLayout, _safe_segment

_FAILURE_CLASSES = {
    "patch_fail",
    "patch_repair_exhausted",
    "syntax_fail",
    "import_fail",
    "smoke_fail",
    "readonly_or_eval_changed",
    "protected_hash_mismatch",
    "dataset_hash_mismatch",
    "job_submit_fail",
    "job_lease_expired",
    "missing_heartbeat",
    "timeout",
    "oom",
    "runtime_exception",
    "metric_missing",
    "metric_invalid",
    "eval_tamper",
    "no_improvement",
    "duplicate_negative_memory",
    "claim_gate_blocked",
    "unknown",
}
_STRATEGIES = {"manual", "best_of_n", "explore", "exploit", "revalidation"}


def _error(error_type: str, message: str, *, recoverable: bool = True, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error_type": error_type, "error": message, "recoverable": recoverable}
    payload.update(extra)
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("trajectory record must be a JSON object")
    return loaded


def _merge_section(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_section(merged[key], value)
        else:
            merged[key] = value
    return merged


class TrajectoryStore:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def create(
        self,
        *,
        quest_id: str,
        env_id: str,
        idea: dict[str, Any],
        strategy: str = "manual",
        parents: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            safe_quest_id = _safe_segment(quest_id, label="quest_id")
            safe_env_id = _safe_segment(env_id, label="env_id")
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        if strategy not in _STRATEGIES:
            return _error("invalid_strategy", f"Unsupported trajectory strategy: {strategy}", recoverable=True)
        if not isinstance(idea, dict) or not idea.get("idea_id"):
            return _error("invalid_schema", "idea.idea_id is required", recoverable=True)
        parent_ids = [str(parent) for parent in (parents or [])]
        created_at = utc_now()
        trajectory_id = f"traj_{uuid4().hex[:16]}"
        record = {
            "schema_version": 1,
            "trajectory_id": trajectory_id,
            "quest_id": safe_quest_id,
            "env_id": safe_env_id,
            "epoch": 0,
            "strategy": strategy,
            "parents": parent_ids,
            "idea": dict(idea),
            "patch": {"status": "not_started", "patch_path": None, "patch_sha256": None, "protected_hashes_ok": None},
            "variant": {"variant_id": None, "workspace_path": None, "package_path": None, "baseline_commit": None},
            "job": {"backend": "none", "job_id": None, "worker_id": None, "resources": {}},
            "result": {"status": "pending", "reward": None, "primary_metric": None, "secondary_metrics": {}, "cost": {"gpu_hours": 0.0, "usd_estimate": 0.0}},
            "failure": {"class": None, "message": None},
            "claimability": {"claim_gate_status": "not_checked", "blocking_reasons": []},
            "lineage": {"parent_trajectory_ids": parent_ids, "mechanism_family": idea.get("mechanism_family"), "novelty_rationale": idea.get("novelty_rationale")},
            "created_at": created_at,
            "updated_at": created_at,
        }
        path = self._trajectory_path(quest_id=safe_quest_id, trajectory_id=trajectory_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.events.write_snapshot(record, path=path)
        self.events.append("trajectory.created", {"quest_id": safe_quest_id, "env_id": safe_env_id, "trajectory_id": trajectory_id})
        return {"ok": True, "quest_id": safe_quest_id, "env_id": safe_env_id, "trajectory_id": trajectory_id, "path": str(path)}

    def update_patch(self, *, quest_id: str, trajectory_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return self._update_section(quest_id=quest_id, trajectory_id=trajectory_id, section="patch", update=patch, event_type="trajectory.patch_updated")

    def update_variant(self, *, quest_id: str, trajectory_id: str, variant: dict[str, Any]) -> dict[str, Any]:
        return self._update_section(quest_id=quest_id, trajectory_id=trajectory_id, section="variant", update=variant, event_type="trajectory.variant_updated")

    def update_job(self, *, quest_id: str, trajectory_id: str, job: dict[str, Any]) -> dict[str, Any]:
        return self._update_section(quest_id=quest_id, trajectory_id=trajectory_id, section="job", update=job, event_type="trajectory.job_updated")

    def update_claimability(self, *, quest_id: str, trajectory_id: str, claimability: dict[str, Any]) -> dict[str, Any]:
        return self._update_section(quest_id=quest_id, trajectory_id=trajectory_id, section="claimability", update=claimability, event_type="trajectory.claimability_updated")

    def update_result(
        self,
        *,
        quest_id: str,
        trajectory_id: str,
        result: dict[str, Any],
        failure: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if failure and failure.get("class") not in _FAILURE_CLASSES:
            return _error("invalid_failure_class", f"Unsupported failure class: {failure.get('class')}", recoverable=True)
        loaded = self._read(quest_id=quest_id, trajectory_id=trajectory_id)
        if loaded["ok"] is False:
            return loaded
        record = loaded["trajectory"]
        record["result"] = _merge_section(record.get("result") or {}, result or {})
        if failure:
            record["failure"] = {"class": failure.get("class"), "message": failure.get("message")}
        record["updated_at"] = utc_now()
        self.events.write_snapshot(record, path=loaded["path"])
        self.events.append("trajectory.result_updated", {"quest_id": record["quest_id"], "env_id": record["env_id"], "trajectory_id": record["trajectory_id"], "status": record["result"].get("status")})
        return {"ok": True, "trajectory_id": record["trajectory_id"], "status": record["result"].get("status")}

    def show(self, *, quest_id: str, trajectory_id: str) -> dict[str, Any]:
        loaded = self._read(quest_id=quest_id, trajectory_id=trajectory_id)
        if loaded["ok"] is False:
            return loaded
        return {"ok": True, "trajectory": self._redact_for_return(loaded["trajectory"])}

    def search(
        self,
        *,
        quest_id: str,
        env_id: str | None = None,
        status: str | None = None,
        positive_only: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        directory = self.layout.state_root / "trajectories"
        if not directory.exists():
            return {"ok": True, "trajectories": []}
        records: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            try:
                record = _load_json(path)
            except (json.JSONDecodeError, ValueError):
                continue
            if env_id is not None and record.get("env_id") != env_id:
                continue
            if status is not None and (record.get("result") or {}).get("status") != status:
                continue
            if positive_only and not self._is_positive(record):
                continue
            records.append(self._redact_for_return(record))
        records.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        safe_limit = max(1, min(int(limit or 20), 100))
        return {"ok": True, "trajectories": records[:safe_limit]}

    def _trajectory_path(self, *, quest_id: str, trajectory_id: str) -> Path:
        safe_trajectory_id = _safe_segment(trajectory_id, label="trajectory_id")
        return self.layout.state_root / "trajectories" / f"{safe_trajectory_id}.json"

    def _read(self, *, quest_id: str, trajectory_id: str) -> dict[str, Any]:
        try:
            path = self._trajectory_path(quest_id=quest_id, trajectory_id=trajectory_id)
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        if not path.exists():
            return _error("trajectory_not_found", f"Trajectory not found: {trajectory_id}", recoverable=True)
        try:
            return {"ok": True, "trajectory": _load_json(path), "path": path}
        except (json.JSONDecodeError, ValueError) as exc:
            return _error("invalid_schema", str(exc), recoverable=True)

    def _update_section(self, *, quest_id: str, trajectory_id: str, section: str, update: dict[str, Any], event_type: str) -> dict[str, Any]:
        loaded = self._read(quest_id=quest_id, trajectory_id=trajectory_id)
        if loaded["ok"] is False:
            return loaded
        if not isinstance(update, dict):
            return _error("invalid_schema", f"{section} update must be an object", recoverable=True)
        record = loaded["trajectory"]
        record[section] = _merge_section(record.get(section) or {}, update)
        record["updated_at"] = utc_now()
        self.events.write_snapshot(record, path=loaded["path"])
        self.events.append(event_type, {"quest_id": record["quest_id"], "env_id": record["env_id"], "trajectory_id": record["trajectory_id"]})
        return {"ok": True, "trajectory_id": record["trajectory_id"]}

    def _is_positive(self, record: dict[str, Any]) -> bool:
        result = record.get("result") or {}
        if result.get("status") != "evaluated":
            return False
        if not (result.get("trusted_primary_metric") is True or result.get("revalidated") is True):
            return False
        metric = result.get("primary_metric") or {}
        if not isinstance(metric, dict) or "value" not in metric:
            return False
        env = EnvironmentService(self.layout).show(quest_id=str(record.get("quest_id")), env_id=str(record.get("env_id")))
        if env.get("ok") is not True:
            return False
        baseline_metric = ((env.get("environment") or {}).get("baseline") or {}).get("baseline_metric") or {}
        baseline_raw = baseline_metric.get("value")
        metric_raw = metric.get("value")
        if baseline_raw is None or metric_raw is None:
            return False
        try:
            baseline_value = float(baseline_raw)
            metric_value = float(metric_raw)
        except (TypeError, ValueError):
            return False
        direction = str(metric.get("direction") or baseline_metric.get("direction") or "maximize")
        if direction == "minimize":
            return metric_value < baseline_value
        return metric_value > baseline_value

    def _redact_for_return(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._redact_value(deepcopy(record))

    def _redact_value(self, value: Any, key: str | None = None) -> Any:
        if isinstance(value, dict):
            return {item_key: self._redact_value(item_value, item_key) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [self._redact_value(item, key) for item in value]
        if isinstance(value, str) and key and key.endswith("path") and Path(value).is_absolute():
            return "[REDACTED_ABSOLUTE_PATH]"
        return value
