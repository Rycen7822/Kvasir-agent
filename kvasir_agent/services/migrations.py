from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .manifest import ManifestService
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _parse_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


class MigrationService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.report_path = layout.state_root / "migrations" / "migration_report.json"

    def migrate_legacy_quests(self) -> dict[str, Any]:
        quests_root = self.layout.state_root / "quests"
        items: list[dict[str, Any]] = []
        for quest_root in sorted(quests_root.iterdir()) if quests_root.exists() else []:
            if not quest_root.is_dir():
                continue
            quest_yaml = quest_root / "quest.yaml"
            quest_json = quest_root / "quest.json"
            if not quest_yaml.exists() and not quest_json.exists():
                continue
            meta = _parse_simple_yaml(quest_yaml)
            if quest_json.exists():
                try:
                    loaded = json.loads(quest_json.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        meta.update({str(k): str(v) for k, v in loaded.items() if isinstance(v, (str, int, float, bool))})
                except json.JSONDecodeError:
                    pass
            items.append(
                {
                    "quest_id": quest_root.name,
                    "title": meta.get("title") or quest_root.name,
                    "goal": meta.get("goal") or meta.get("title") or quest_root.name,
                    "source_path": str(quest_root),
                    "source_preserved": True,
                    "migrated_at": _utc_now(),
                }
            )
        manifest_service = ManifestService(self.layout)
        if items and not manifest_service.path.exists():
            first = items[0]
            manifest_service.write(manifest_service.default_manifest(name=first["title"], goal=first["goal"]))
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {"ok": True, "migrated_count": len(items), "items": items, "created_at": _utc_now()}
        self.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.events.append("migration.legacy_quests", {"migrated_count": len(items)})
        return {"ok": True, "migrated_count": len(items), "items": items, "report_path": str(self.report_path)}
