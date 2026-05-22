from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from .event_store import EventStore
from .legacy_migration import LegacyQuestDetector, RootBoundLegacyMigrator, normalize_legacy_quest_id
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _safe_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _read_yaml_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        quarantine = path.with_name(f"{path.name}.corrupt.{_safe_timestamp()}")
        path.replace(quarantine)
        return {}
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        quarantine = path.with_name(f"{path.name}.corrupt.{_safe_timestamp()}")
        path.replace(quarantine)
        return {}
    return dict(loaded)


def _write_yaml_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    tmp.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(path)


class ManifestService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.path = layout.research.manifest_path
        self.events = EventStore(layout)

    def default_manifest(self, *, name: str, goal: str) -> dict[str, Any]:
        created_at = _utc_now()
        quest_id = f"qst_{uuid4().hex[:12]}"
        return {
            "schema_version": 2,
            "layout_mode": "root_bound",
            "project": {
                "name": name,
                "root": str(self.layout.project_root),
                "owner": "local",
                "created_at": created_at,
            },
            "quest": {
                "id": quest_id,
                "root_bound": True,
                "title": goal,
                "created_by": "codexscientist-plugin",
                "created_at": created_at,
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
                "schema_version": 2,
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

    def _normalize_manifest(self, manifest: dict[str, Any], *, inferred_goal: str | None = None) -> dict[str, Any]:
        default = self.default_manifest(
            name=str((manifest.get("project") or {}).get("name") or self.layout.project_root.name),
            goal=str((manifest.get("goal") or {}).get("title") or inferred_goal or self.layout.project_root.name),
        )
        merged = dict(default)
        for key, value in manifest.items():
            if key in {"schema_version", "layout_mode", "project", "quest", "state"}:
                continue
            merged[key] = value
        project = dict(default["project"])
        if isinstance(manifest.get("project"), dict):
            project.update(manifest["project"])
        project["root"] = str(self.layout.project_root)
        project.setdefault("created_at", default["project"]["created_at"])
        quest = dict(default["quest"])
        if isinstance(manifest.get("quest"), dict):
            quest.update(manifest["quest"])
        quest["root_bound"] = True
        quest.setdefault("id", default["quest"]["id"])
        quest.setdefault("title", str((merged.get("goal") or {}).get("title") or inferred_goal or self.layout.project_root.name))
        state = dict(default["state"])
        if isinstance(manifest.get("state"), dict):
            state.update(manifest["state"])
        state["schema_version"] = 2
        return {
            "schema_version": 2,
            "layout_mode": "root_bound",
            "project": project,
            "quest": quest,
            **{key: value for key, value in merged.items() if key not in {"schema_version", "layout_mode", "project", "quest", "state"}},
            "state": state,
        }

    def write(self, manifest: dict[str, Any]) -> None:
        self.layout.ensure_research_layout()
        _write_yaml_atomic(self.path, self._normalize_manifest(manifest))

    def init(self, *, name: str, goal: str, overwrite: bool = False) -> dict[str, Any]:
        if self.path.exists() and not overwrite:
            return {"ok": False, "error": "Manifest already exists", "error_type": "manifest_exists", "recoverable": True, "path": str(self.path)}
        manifest = self.default_manifest(name=name, goal=goal)
        self.write(manifest)
        self.events.append("manifest.initialized", {"path": str(self.path), "name": name})
        return {"ok": True, "path": str(self.path), "manifest": manifest}

    def ensure_initialized(
        self,
        *,
        create: bool,
        inferred_goal: str | None = None,
        write_reason: str | None = None,
        quest_id: str | None = None,
    ) -> dict[str, Any]:
        if self.path.exists():
            manifest = self._normalize_manifest(_read_yaml_manifest(self.path), inferred_goal=inferred_goal)
            _write_yaml_atomic(self.path, manifest)
            return {"ok": True, "path": str(self.path), "manifest": manifest, "created": False}
        legacy_status = LegacyQuestDetector.inspect(self.layout)
        if not create:
            return {
                "ok": False,
                "error_type": "no_research_state",
                "recoverable": True,
                "path": str(self.path),
                **legacy_status.as_dict(),
            }
        if legacy_status.status == "multiple_legacy_quests_blocked":
            return {
                "ok": False,
                "error": "Multiple legacy CodexScientist quests require manual migration before writing root-bound state.",
                "error_type": "multiple_legacy_quests_blocked",
                "recoverable": True,
                "path": str(self.path),
                **legacy_status.as_dict(),
            }
        if legacy_status.status == "single_legacy_detected":
            legacy_quest = legacy_status.quests[0]
            migrated_quest_id, quest_id_mapping = normalize_legacy_quest_id(legacy_quest.quest_id, fallback=legacy_quest.path.name)
            supplied_quest_id = str(quest_id or "").strip()
            if supplied_quest_id and supplied_quest_id != migrated_quest_id:
                return {
                    "ok": False,
                    "error": f"supplied quest_id {supplied_quest_id!r} does not match single legacy provenance id {migrated_quest_id!r}",
                    "error_type": "root_bound_quest_id_mismatch",
                    "recoverable": True,
                    "supplied_quest_id": supplied_quest_id,
                    "manifest_quest_id": migrated_quest_id,
                    **legacy_status.as_dict(),
                }
            migration = RootBoundLegacyMigrator(self.layout).import_single(legacy_quest, quest_id_mapping=quest_id_mapping)
            if not migration.get("ok"):
                return {**migration, **legacy_status.as_dict()}
            manifest = self.default_manifest(name=self.layout.project_root.name, goal=legacy_quest.title or inferred_goal or self.layout.project_root.name)
            manifest["quest"]["id"] = migrated_quest_id
            manifest["quest"]["title"] = legacy_quest.title
            manifest["goal"]["title"] = legacy_quest.title
            try:
                source_rel = legacy_quest.path.relative_to(self.layout.project_root).as_posix()
            except ValueError:
                source_rel = str(legacy_quest.path)
            manifest["legacy"] = {
                "migrated_from": source_rel,
                "source_preserved": True,
                "migrated_at": _utc_now(),
                "original_quest_id": legacy_quest.quest_id,
            }
            if quest_id_mapping:
                manifest["legacy"]["quest_id_mapping"] = quest_id_mapping
            self.write(manifest)
            self.events.append(
                "migration.root_bound_single_legacy_imported",
                {"source": source_rel, "quest_id": migrated_quest_id, "report_path": migration.get("report_path")},
                idempotency_key=f"migration.single_legacy:{source_rel}",
            )
            return {
                "ok": True,
                "path": str(self.path),
                "manifest": manifest,
                "created": True,
                "migrated": True,
                "migration_report_path": migration.get("report_path"),
                **legacy_status.as_dict(),
            }
        manifest = self.default_manifest(name=self.layout.project_root.name, goal=inferred_goal or self.layout.project_root.name)
        supplied_quest_id = str(quest_id or "").strip()
        if supplied_quest_id:
            manifest["quest"]["id"] = supplied_quest_id
        self.write(manifest)
        self.events.append(
            "research.initialized",
            {"path": str(self.path), "write_reason": write_reason or "first_durable_write", "quest_id": manifest["quest"]["id"]},
            idempotency_key=f"research.initialized:{self.path}",
        )
        return {"ok": True, "path": str(self.path), "manifest": manifest, "created": True}

    def quest_identity(self, *, create: bool = False) -> dict[str, Any]:
        result = self.ensure_initialized(create=create)
        if not result.get("ok"):
            return result
        manifest = result["manifest"]
        return {
            "ok": True,
            "quest_id": manifest["quest"]["id"],
            "quest_root": str(self.layout.state_root),
            "project_root": str(self.layout.project_root),
            "layout_mode": "root_bound",
        }

    def read(self) -> dict[str, Any]:
        return _read_yaml_manifest(self.path)

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
