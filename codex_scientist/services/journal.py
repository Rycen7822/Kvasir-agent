from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .event_store import EventStore
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class JournalService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.path = layout.state_root / "wiki" / "negative_memory.jsonl"

    def record_negative_result(self, *, trial_id: str, idea_id: str, failure_reason: str, lesson: str) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "record_id": uuid4().hex,
            "trial_id": trial_id,
            "idea_id": idea_id,
            "failure_reason": failure_reason,
            "lesson": lesson,
            "created_at": _utc_now(),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        self.events.append("journal.negative_result", {"trial_id": trial_id, "idea_id": idea_id})
        return record

    def list_negative_memory(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def record_stage_reflection(self, *, trigger: str, gaps: list[str], next_sources: list[str]) -> dict[str, Any]:
        reflections_dir = self.layout.state_root / "journals"
        reflections_dir.mkdir(parents=True, exist_ok=True)
        path = reflections_dir / "stage_progress.json"
        plan_update = {
            "trigger": trigger,
            "gaps": list(gaps),
            "next_sources": list(next_sources),
            "status": "needs_user_decision",
            "created_running_trial": False,
            "updated_at": _utc_now(),
        }
        path.write_text(json.dumps(plan_update, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.events.append("journal.stage_reflection", {"trigger": trigger, "status": plan_update["status"]})
        return {"ok": True, "path": str(path), "plan_update": plan_update}
