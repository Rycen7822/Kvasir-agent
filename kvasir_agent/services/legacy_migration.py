from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .project_state import ProjectLayout


_QUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_METADATA_NAMES = {"quest.yaml", "quest.yml", "quest.json"}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _read_legacy_metadata(path: Path) -> dict[str, Any]:
    try:
        if path.suffix == ".json":
            loaded = json.loads(path.read_text(encoding="utf-8"))
        else:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _metadata_path_for(quest_root: Path) -> Path | None:
    for name in ("quest.yaml", "quest.yml", "quest.json"):
        path = quest_root / name
        if path.is_file():
            return path
    return None


def _goal_title(metadata: dict[str, Any], fallback: str) -> str:
    goal = metadata.get("goal")
    if isinstance(goal, dict) and str(goal.get("title") or "").strip():
        return str(goal.get("title")).strip()
    for key in ("title", "name", "goal"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def normalize_legacy_quest_id(value: str | None, *, fallback: str) -> tuple[str, dict[str, str] | None]:
    raw = str(value or fallback or "").strip()
    if raw and _QUEST_ID_RE.match(raw) and raw not in {".", ".."}:
        return raw, None
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._-") or re.sub(r"[^A-Za-z0-9_.-]+", "_", fallback).strip("._-") or "legacy"
    if not _QUEST_ID_RE.match(normalized) or normalized in {".", ".."}:
        normalized = "legacy"
    return f"qst_{normalized[:48]}", {"from": raw, "to": f"qst_{normalized[:48]}"}


@dataclass(frozen=True)
class LegacyQuestInfo:
    quest_id: str
    title: str
    updated_at: str | None
    path: Path
    metadata_path: Path
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "title": self.title,
            "updated_at": self.updated_at,
            "path": str(self.path),
            "metadata_path": str(self.metadata_path),
        }


@dataclass(frozen=True)
class LegacyQuestStatus:
    status: str
    quests: tuple[LegacyQuestInfo, ...]

    @property
    def count(self) -> int:
        return len(self.quests)

    def as_dict(self) -> dict[str, Any]:
        return {"legacy_status": self.status, "legacy_quest_ids": [quest.quest_id for quest in self.quests], "legacy_quests": [quest.as_dict() for quest in self.quests]}


class LegacyQuestDetector:
    """Detect legacy quest registry inputs without consulting active/latest session state."""

    @staticmethod
    def inspect(layout: ProjectLayout) -> LegacyQuestStatus:
        legacy_dir = layout.legacy_quests_dir
        if not legacy_dir.exists():
            return LegacyQuestStatus(status="none", quests=())
        quests: list[LegacyQuestInfo] = []
        for quest_root in sorted(path for path in legacy_dir.iterdir() if path.is_dir()):
            metadata_path = _metadata_path_for(quest_root)
            if metadata_path is None:
                continue
            metadata = _read_legacy_metadata(metadata_path)
            quest_id = str(metadata.get("quest_id") or metadata.get("id") or quest_root.name).strip() or quest_root.name
            quests.append(
                LegacyQuestInfo(
                    quest_id=quest_id,
                    title=_goal_title(metadata, quest_id),
                    updated_at=str(metadata.get("updated_at") or metadata.get("modified_at") or metadata.get("created_at") or "").strip() or None,
                    path=quest_root,
                    metadata_path=metadata_path,
                    metadata=metadata,
                )
            )
        status = "none"
        if len(quests) == 1:
            status = "single_legacy_detected"
        elif len(quests) > 1:
            status = "multiple_legacy_quests_blocked"
        return LegacyQuestStatus(status=status, quests=tuple(quests))


class RootBoundLegacyMigrator:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.migrations_dir = layout.state_root / "migrations"
        self.report_path = self.migrations_dir / "root_bound_migration_report.json"
        self.conflicts_path = self.migrations_dir / "root_bound_conflicts.json"

    def _source_rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.layout.project_root).as_posix()
        except ValueError:
            return path.as_posix()

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def import_single(self, quest: LegacyQuestInfo, *, quest_id_mapping: dict[str, str] | None = None) -> dict[str, Any]:
        self.layout.ensure_research_layout()
        imported_paths: list[str] = []
        skipped_paths: list[str] = []
        conflicts: list[dict[str, str]] = []
        for source in sorted(path for path in quest.path.rglob("*") if path.is_file()):
            if source.parent == quest.path and source.name in _METADATA_NAMES:
                skipped_paths.append(source.name)
                continue
            relative = source.relative_to(quest.path)
            dest = self.layout.state_root / relative
            rel_text = relative.as_posix()
            if dest.exists():
                same_file = dest.is_file() and source.read_bytes() == dest.read_bytes()
                if same_file:
                    skipped_paths.append(rel_text)
                else:
                    conflicts.append({"relative_path": rel_text, "source": str(source), "destination": str(dest)})
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            imported_paths.append(rel_text)
        report = {
            "schema_version": 1,
            "status": "blocked" if conflicts else "imported",
            "source": self._source_rel(quest.path),
            "source_preserved": True,
            "imported_paths": imported_paths,
            "skipped_paths": skipped_paths,
            "conflicts": conflicts,
            "updated_at": _utc_now(),
        }
        if quest_id_mapping:
            report["quest_id_mapping"] = dict(quest_id_mapping)
        self._write_json(self.report_path, report)
        if conflicts:
            conflict_payload = {"schema_version": 1, "status": "blocked", "source": report["source"], "conflicts": conflicts, "updated_at": report["updated_at"]}
            if quest_id_mapping:
                conflict_payload["quest_id_mapping"] = dict(quest_id_mapping)
            self._write_json(self.conflicts_path, conflict_payload)
            return {"ok": False, "error": "Legacy migration conflicts require manual resolution", "error_type": "migration_conflict", "recoverable": True, "report_path": str(self.report_path), "conflicts_path": str(self.conflicts_path), "conflicts": conflicts, "legacy_quest": quest.as_dict()}
        if self.conflicts_path.exists():
            self.conflicts_path.unlink()
        return {"ok": True, "report_path": str(self.report_path), "report": report, "legacy_quest": quest.as_dict()}
