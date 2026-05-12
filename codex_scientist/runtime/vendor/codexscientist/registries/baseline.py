from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..artifact.metrics import normalize_metric_contract, normalize_metrics_summary
from ..shared import append_jsonl, ensure_dir, read_jsonl, read_yaml, resolve_within, utc_now, write_yaml


_BASELINE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class BaselineRegistry:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.root = ensure_dir(home / "config" / "baselines")
        self.entries_root = ensure_dir(self.root / "entries")
        self.index_path = self.root / "index.jsonl"

    def list_entries(self) -> list[dict]:
        self.reconcile_confirmed_quests()
        entry_files = sorted(self.entries_root.glob("*.yaml"))
        if entry_files:
            return sorted(
                (
                    entry
                    for path in entry_files
                    for entry in [self._load_entry_file(path)]
                    if not self._is_deleted_entry(entry)
                ),
                key=self._entry_sort_key,
            )

        latest_by_id: dict[str, dict] = {}
        for item in self._history_entries():
            baseline_id = str(item.get("baseline_id") or item.get("entry_id") or "").strip()
            if baseline_id:
                latest_by_id[baseline_id] = item
        return sorted(
            (item for item in latest_by_id.values() if not self._is_deleted_entry(item)),
            key=self._entry_sort_key,
        )

    def get(self, baseline_id: str, *, include_deleted: bool = False) -> dict | None:
        normalized_id = self._normalize_identifier(baseline_id, field_name="Baseline id")
        path = self._entry_path(normalized_id)
        if path.exists():
            entry = self._load_entry_file(path)
            if self._is_deleted_entry(entry) and not include_deleted:
                return None
            return entry
        latest_match = None
        for item in self._history_entries():
            if item.get("baseline_id") == normalized_id or item.get("entry_id") == normalized_id:
                latest_match = item
        if self._is_deleted_entry(latest_match) and not include_deleted:
            return None
        return latest_match

    def is_deleted(self, baseline_id: str) -> bool:
        try:
            entry = self.get(baseline_id, include_deleted=True)
        except ValueError:
            return False
        return self._is_deleted_entry(entry)

    def publish(self, entry: dict) -> dict:
        timestamp = utc_now()
        baseline_id = self._normalize_identifier(
            entry.get("baseline_id") or entry.get("entry_id") or "",
            field_name="Baseline id",
        )
        if not baseline_id:
            raise ValueError("Baseline entry requires baseline_id or entry_id")
        existing = self.get(baseline_id) or {}
        baseline_variants = self._normalize_variants(entry.get("baseline_variants") or existing.get("baseline_variants") or [])
        default_variant_id = entry.get("default_variant_id", existing.get("default_variant_id"))
        if baseline_variants and default_variant_id is None and len(baseline_variants) == 1:
            default_variant_id = baseline_variants[0]["variant_id"]
        if default_variant_id is not None:
            default_variant_id = self._normalize_identifier(
                default_variant_id,
                field_name="Default baseline variant id",
            )
            if baseline_variants and default_variant_id not in {item["variant_id"] for item in baseline_variants}:
                raise ValueError(
                    f"Default baseline variant `{default_variant_id}` is not present in baseline_variants."
                )
        if not baseline_variants:
            default_variant_id = None
        metric_contract = normalize_metric_contract(
            entry.get("metric_contract") or existing.get("metric_contract"),
            baseline_id=baseline_id,
            metrics_summary=entry.get("metrics_summary") or existing.get("metrics_summary"),
            primary_metric=entry.get("primary_metric") or existing.get("primary_metric"),
            baseline_variants=baseline_variants,
        )
        normalized = {
            **existing,
            **entry,
            "registry_kind": "baseline",
            "schema_version": 1,
            "entry_id": baseline_id,
            "baseline_id": baseline_id,
            "status": entry.get("status") or existing.get("status", "active"),
            "created_at": existing.get("created_at") or entry.get("created_at", timestamp),
            "updated_at": timestamp,
            "metrics_summary": normalize_metrics_summary(entry.get("metrics_summary") or existing.get("metrics_summary")),
            "baseline_variants": baseline_variants,
            "default_variant_id": default_variant_id,
            "metric_contract": metric_contract,
        }
        write_yaml(self._entry_path(baseline_id), normalized)
        append_jsonl(self.index_path, normalized)
        return normalized

    def reconcile_confirmed_quests(self) -> list[dict]:
        quests_root = self.home / "quests"
        if not quests_root.exists():
            return []

        synchronized: list[dict] = []
        for quest_yaml in sorted(quests_root.glob("*/quest.yaml")):
            quest_root = quest_yaml.parent
            payload = read_yaml(quest_yaml, {})
            if not isinstance(payload, dict):
                continue
            if str(payload.get("baseline_gate") or "").strip().lower() != "confirmed":
                continue

            confirmed_ref = (
                dict(payload.get("confirmed_baseline_ref") or {})
                if isinstance(payload.get("confirmed_baseline_ref"), dict)
                else {}
            )
            baseline_id = str(confirmed_ref.get("baseline_id") or "").strip()
            if not baseline_id:
                continue

            baseline_root_rel_path = str(confirmed_ref.get("baseline_root_rel_path") or "").strip()
            if baseline_root_rel_path:
                try:
                    baseline_root = resolve_within(quest_root, baseline_root_rel_path)
                except ValueError:
                    baseline_root = quest_root / "baselines" / "local" / baseline_id
            else:
                source_mode = str(confirmed_ref.get("source_mode") or "").strip().lower()
                if source_mode == "imported":
                    baseline_root = quest_root / "baselines" / "imported" / baseline_id
                else:
                    baseline_root = quest_root / "baselines" / "local" / baseline_id

            attachment_path = quest_root / "baselines" / "imported" / baseline_id / "attachment.yaml"
            attachment = read_yaml(attachment_path, {}) if attachment_path.exists() else {}
            attachment_entry = (
                dict(attachment.get("entry") or {})
                if isinstance(attachment, dict) and isinstance(attachment.get("entry"), dict)
                else {}
            )
            selected_variant = (
                dict(attachment.get("selected_variant") or {})
                if isinstance(attachment, dict) and isinstance(attachment.get("selected_variant"), dict)
                else {}
            )

            normalized_variant_id = str(
                confirmed_ref.get("variant_id")
                or selected_variant.get("variant_id")
                or attachment_entry.get("default_variant_id")
                or ""
            ).strip() or None
            metrics_summary = normalize_metrics_summary(attachment_entry.get("metrics_summary"))
            baseline_variants = attachment_entry.get("baseline_variants")
            if not isinstance(baseline_variants, list):
                baseline_variants = []
            if normalized_variant_id and not baseline_variants:
                baseline_variants = [
                    {
                        "variant_id": normalized_variant_id,
                        "label": normalized_variant_id,
                        "metrics_summary": metrics_summary,
                    }
                ]

            source_baseline_path = str(
                attachment_entry.get("path")
                or confirmed_ref.get("baseline_path")
                or baseline_root
            ).strip()
            source_path = Path(source_baseline_path).expanduser()
            materializable = source_path.is_dir()
            entry = {
                **attachment_entry,
                "baseline_id": baseline_id,
                "entry_id": baseline_id,
                "status": "quest_confirmed",
                "summary": (
                    str(attachment_entry.get("summary") or "").strip()
                    or f"Confirmed baseline from quest `{quest_root.name}`."
                ),
                "path": str(source_path),
                "source_mode": str(confirmed_ref.get("source_mode") or attachment_entry.get("source_mode") or "").strip()
                or ("imported" if "baselines/imported/" in baseline_root.as_posix() else "local"),
                "source_quest_id": quest_root.name,
                "source_baseline_path": str(source_path),
                "confirmed_at": str(
                    confirmed_ref.get("confirmed_at") or payload.get("updated_at") or attachment_entry.get("updated_at") or utc_now()
                ),
                "selected_variant_id": normalized_variant_id,
                "materializable": materializable,
                "availability": "ready" if materializable else "missing",
                "default_variant_id": attachment_entry.get("default_variant_id") or normalized_variant_id,
                "baseline_variants": baseline_variants,
                "metric_contract": normalize_metric_contract(
                    attachment_entry.get("metric_contract"),
                    baseline_id=baseline_id,
                    metrics_summary=metrics_summary,
                    primary_metric=attachment_entry.get("primary_metric"),
                    baseline_variants=baseline_variants,
                ),
                "primary_metric": attachment_entry.get("primary_metric"),
                "metrics_summary": metrics_summary,
            }

            existing = self._existing_entry(baseline_id)
            if self._is_deleted_entry(existing):
                continue
            if self._entry_needs_publish(existing, entry):
                synchronized.append(self.publish(entry))
            elif existing:
                synchronized.append(existing)
        return synchronized

    def attach(self, quest_root: Path, baseline_id: str, variant_id: str | None = None) -> dict:
        normalized_baseline_id = self._normalize_identifier(baseline_id, field_name="Baseline id")
        entry = self.get(normalized_baseline_id)
        if not entry:
            raise FileNotFoundError(f"Unknown baseline: {normalized_baseline_id}")
        selected_variant = None
        variants = entry.get("baseline_variants") or []
        if variant_id:
            normalized_variant_id = self._normalize_identifier(variant_id, field_name="Baseline variant id")
            for variant in variants:
                if variant.get("variant_id") == normalized_variant_id:
                    selected_variant = variant
                    break
            if selected_variant is None:
                raise FileNotFoundError(f"Unknown baseline variant: {normalized_variant_id}")
        elif variants:
            default_variant_id = entry.get("default_variant_id")
            if default_variant_id:
                selected_variant = next((item for item in variants if item.get("variant_id") == default_variant_id), None)
                if selected_variant is None:
                    raise ValueError(
                        f"Baseline `{normalized_baseline_id}` points to missing default variant `{default_variant_id}`."
                    )
            else:
                selected_variant = variants[0]

        attachment_root = ensure_dir(self._attachment_root(quest_root, normalized_baseline_id))
        attachment = {
            "attached_at": utc_now(),
            "source_baseline_id": normalized_baseline_id,
            "source_variant_id": selected_variant.get("variant_id") if selected_variant else None,
            "entry": entry,
            "selected_variant": selected_variant,
        }
        write_yaml(attachment_root / "attachment.yaml", attachment)
        return attachment

    def delete(self, baseline_id: str) -> dict:
        normalized_id = self._normalize_identifier(baseline_id, field_name="Baseline id")
        existing = self.get(normalized_id, include_deleted=True) or {}
        timestamp = utc_now()
        deleted_entry = {
            **existing,
            "registry_kind": "baseline",
            "schema_version": 1,
            "entry_id": normalized_id,
            "baseline_id": normalized_id,
            "status": "deleted",
            "updated_at": timestamp,
            "deleted_at": timestamp,
            "summary": str(existing.get("summary") or "").strip(),
        }
        if not deleted_entry.get("created_at"):
            deleted_entry["created_at"] = timestamp
        write_yaml(self._entry_path(normalized_id), deleted_entry)
        append_jsonl(self.index_path, deleted_entry)
        return deleted_entry

    def _history_entries(self) -> list[dict]:
        return read_jsonl(self.index_path)

    def _entry_path(self, baseline_id: str) -> Path:
        return resolve_within(self.entries_root, f"{baseline_id}.yaml")

    @staticmethod
    def _attachment_root(quest_root: Path, baseline_id: str) -> Path:
        return resolve_within(quest_root / "baselines" / "imported", baseline_id)

    @staticmethod
    def _entry_sort_key(entry: dict) -> tuple[str, str]:
        return (
            str(entry.get("updated_at") or entry.get("created_at") or ""),
            str(entry.get("baseline_id") or entry.get("entry_id") or ""),
        )

    @staticmethod
    def _normalize_identifier(value: object, *, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized or not _BASELINE_ID_PATTERN.fullmatch(normalized):
            raise ValueError(
                f"{field_name} must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`."
            )
        return normalized

    def _load_entry_file(self, path: Path) -> dict:
        payload = read_yaml(path, {})
        if isinstance(payload, dict) and payload:
            return payload
        baseline_id = path.stem
        return {
            "registry_kind": "baseline",
            "schema_version": 1,
            "entry_id": baseline_id,
            "baseline_id": baseline_id,
            "status": "unhealthy",
            "path": str(path),
            "summary": "Registry entry could not be loaded as a mapping.",
        }

    def _existing_entry(self, baseline_id: str) -> dict[str, Any] | None:
        path = self._entry_path(baseline_id)
        if not path.exists():
            return None
        entry = self._load_entry_file(path)
        return entry if isinstance(entry, dict) and entry else None

    @staticmethod
    def _is_deleted_entry(entry: dict[str, Any] | None) -> bool:
        if not isinstance(entry, dict):
            return False
        return str(entry.get("status") or "").strip().lower() == "deleted"

    @staticmethod
    def _entry_needs_publish(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> bool:
        if not existing:
            return True
        tracked_fields = (
            "status",
            "summary",
            "path",
            "source_mode",
            "source_quest_id",
            "source_baseline_path",
            "confirmed_at",
            "selected_variant_id",
            "materializable",
            "availability",
            "default_variant_id",
            "baseline_variants",
            "metric_contract",
            "primary_metric",
            "metrics_summary",
        )
        return any(existing.get(field) != candidate.get(field) for field in tracked_fields)

    def _normalize_variants(self, variants: list[dict]) -> list[dict]:
        normalized_variants: list[dict] = []
        seen_variant_ids: set[str] = set()
        for index, variant in enumerate(variants):
            if not isinstance(variant, dict):
                raise ValueError(f"Baseline variant #{index + 1} must be a mapping.")
            variant_id = self._normalize_identifier(
                variant.get("variant_id"),
                field_name="Baseline variant id",
            )
            if variant_id in seen_variant_ids:
                raise ValueError(f"Duplicate baseline variant id `{variant_id}`.")
            seen_variant_ids.add(variant_id)
            normalized_variants.append(
                {
                    **variant,
                    "variant_id": variant_id,
                    "metrics_summary": normalize_metrics_summary(variant.get("metrics_summary")),
                }
            )
        return normalized_variants
