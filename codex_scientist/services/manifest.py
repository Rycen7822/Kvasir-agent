from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ManifestService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.path = layout.state_root / "research.yaml"
        self.events = EventStore(layout)

    def default_manifest(self, *, name: str, goal: str) -> dict[str, Any]:
        return {
            "project": {
                "name": name,
                "root": str(self.layout.project_root),
                "owner": "local",
                "created_at": _utc_now(),
            },
            "goal": {"title": goal, "success_criteria": [], "non_goals": []},
            "autonomy": {
                "mode": "copilot",
                "decision_policy": "user_gated",
                "autonomous_idea_improvement": False,
                "enable_when": "explicit_user_request",
                "require_human_review_for_new_ideas": True,
            },
            "paths": {
                "editable_paths": ["src/**"],
                "readonly_paths": ["data/**", "eval/**"],
                "eval_paths": ["eval/**"],
                "artifact_paths": ["artifacts/**", "results/**"],
                "exclude_paths": ["CodexScientist/**", ".git/**"],
                "reference_repo_paths": [],
                "path_integrity": {
                    "require_clean_git_before_trial": True,
                    "forbid_untracked_eval_changes": True,
                    "dirty_state_policy": "block",
                },
            },
            "baselines": {"required": True, "entries": []},
            "metrics": {
                "primary": {
                    "id": "primary",
                    "name": "primary",
                    "direction": "maximize",
                    "extractor": "jsonpath",
                    "validation": {"finite": True, "range": [None, None], "required_artifacts": []},
                    "aggregation": {"seeds": "mean", "promotion_requires": "multi_seed"},
                },
                "secondary": [],
            },
            "budgets": {
                "wall_time_per_trial": "1h",
                "max_trials_per_day": 8,
                "max_failed_retries": 1,
                "max_cost_usd_per_day": 0,
                "max_tokens_per_day": 0,
                "gpu_hours_per_day": None,
                "context": {
                    "max_status_chars": 4000,
                    "max_context_pack_chars": 12000,
                    "max_query_pack_chars": 12000,
                    "max_log_tail_lines": 80,
                },
            },
            "queue": {
                "backend": "local_process",
                "max_parallel": 1,
                "lease_ttl": "30m",
                "phases": [],
                "terminal_statuses": [
                    "completed",
                    "failed_metric",
                    "failed_artifact",
                    "failed_other",
                    "failed_readonly",
                    "failed_timeout",
                    "cancelled",
                    "stuck",
                ],
                "retry_policy": {"oom": 1, "transient": 1, "failed_other": 0},
            },
            "review": {"enabled": True, "mode": "read_only", "trigger": "pre_claim"},
            "novelty": {
                "check_failed_ideas": True,
                "check_reference_overlap": True,
                "require_mechanism": True,
                "min_grounding_refs": 0,
            },
            "safety": {
                "require_clean_git_before_trial": True,
                "allow_destructive_git": False,
                "redact_logs": True,
                "raw_log_return_limit_lines": 80,
            },
            "state": {
                "schema_version": 1,
                "atomic_write": True,
                "event_ledger": "events/events.jsonl",
                "corruption_quarantine": True,
                "snapshot_retention": {
                    "keep_latest_per_thread": 3,
                    "keep_daily_rollups": 10,
                    "prune_large_checkpoints": True,
                },
            },
        }

    def write(self, manifest: dict[str, Any]) -> None:
        self.layout.ensure_core_dirs()
        self.events.write_snapshot(manifest, self.path)

    def init(self, *, name: str, goal: str, overwrite: bool = False) -> dict[str, Any]:
        if self.path.exists() and not overwrite:
            return {"ok": False, "error": "Manifest already exists", "error_type": "manifest_exists", "recoverable": True, "path": str(self.path)}
        manifest = self.default_manifest(name=name, goal=goal)
        self.write(manifest)
        self.events.append("manifest.initialized", {"path": str(self.path), "name": name})
        return {"ok": True, "path": str(self.path), "manifest": manifest}

    def read(self) -> dict[str, Any]:
        return self.events.read_snapshot(default={}, path=self.path)

    def validate(self) -> dict[str, Any]:
        manifest = self.read()
        errors: list[str] = []
        if not manifest:
            errors.append("manifest")
        for key in ("project", "goal", "autonomy", "paths", "baselines", "metrics", "state"):
            if key not in manifest:
                errors.append(key)
        metrics = manifest.get("metrics") if isinstance(manifest.get("metrics"), dict) else {}
        primary = metrics.get("primary") if isinstance(metrics, dict) else None
        if not isinstance(primary, dict):
            errors.append("metrics.primary")
        baseline_ready = self.baseline_ready(manifest)
        return {"ok": not errors, "errors": errors, "baseline_ready": baseline_ready, "path": str(self.path), "manifest": manifest}

    def record_baseline(
        self,
        *,
        baseline_id: str,
        status: str,
        metric_contract: str = "primary",
        waiver_reason: str | None = None,
        artifact_requirements: list[str] | None = None,
    ) -> dict[str, Any]:
        manifest = self.read()
        if not manifest:
            return {"ok": False, "error": "Manifest missing", "error_type": "manifest_missing", "recoverable": True}
        baselines = manifest.setdefault("baselines", {"required": True, "entries": []})
        entries = baselines.setdefault("entries", [])
        baseline = {
            "id": baseline_id,
            "status": status,
            "metric_contract": metric_contract,
            "artifact_requirements": artifact_requirements or [],
            "waiver_reason": waiver_reason,
            "updated_at": _utc_now(),
        }
        entries[:] = [entry for entry in entries if not (isinstance(entry, dict) and entry.get("id") == baseline_id)]
        entries.append(baseline)
        self.write(manifest)
        self.events.append("baseline.recorded", {"id": baseline_id, "status": status})
        return {"ok": True, "path": str(self.path), "baseline": baseline, "manifest": manifest, "baseline_ready": self.baseline_ready(manifest)}

    @staticmethod
    def baseline_ready(manifest: dict[str, Any]) -> bool:
        baselines = manifest.get("baselines") if isinstance(manifest.get("baselines"), dict) else {}
        if not baselines.get("required", True):
            return True
        for entry in baselines.get("entries") or []:
            if isinstance(entry, dict) and entry.get("status") in {"confirmed", "waived"}:
                return True
        return False
