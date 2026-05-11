from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .project_state import ProjectLayout

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _safe_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


class EventStore:
    """Small append-only JSONL event store plus atomic snapshot helper."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.path = layout.event_log_path

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.layout.ensure_core_dirs()
        event = {
            "schema_version": SCHEMA_VERSION,
            "event_id": uuid4().hex,
            "event_type": str(event_type),
            "created_at": utc_now(),
            "payload": dict(payload),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def read_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                loaded = json.loads(line)
                if isinstance(loaded, dict):
                    events.append(loaded)
        return events

    def write_snapshot(self, snapshot: dict[str, Any], path: Path | None = None) -> None:
        target = path or self.layout.project_state_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
        tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(target)

    def read_snapshot(self, default: dict[str, Any] | None = None, path: Path | None = None) -> dict[str, Any]:
        target = path or self.layout.project_state_path
        if not target.exists():
            return dict(default or {})
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            quarantine = target.with_name(f"{target.name}.corrupt.{_safe_timestamp()}")
            target.replace(quarantine)
            return dict(default or {})
        if not isinstance(loaded, dict):
            return dict(default or {})
        return loaded
