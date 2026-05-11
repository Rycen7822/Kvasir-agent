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


class FrontierService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.path = layout.state_root / "wiki" / "frontier.json"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"candidates": {}}
        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {"candidates": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def add_candidate(self, idea_id: str, *, score: float, source: str, title: str | None = None) -> dict[str, Any]:
        data = self._read()
        candidates = data.setdefault("candidates", {})
        candidate = {
            "idea_id": idea_id,
            "score": float(score),
            "source": source,
            "title": title or idea_id,
            "status": "candidate",
            "claim_status": "not_claimable",
            "created_at": _utc_now(),
        }
        candidates[idea_id] = candidate
        self._write(data)
        self.events.append("frontier.candidate_added", {"idea_id": idea_id, "score": score, "source": source})
        return candidate

    def select(self, *, limit: int) -> list[dict[str, Any]]:
        candidates = list((self._read().get("candidates") or {}).values())
        candidates.sort(key=lambda item: (-float(item.get("score", 0.0)), str(item.get("idea_id", ""))))
        return candidates[:limit]

    def promote(self, idea_id: str, *, evidence_level: str) -> dict[str, Any]:
        data = self._read()
        candidate = data.setdefault("candidates", {}).get(idea_id)
        if not isinstance(candidate, dict):
            return {"ok": False, "error": "Unknown candidate", "error_type": "unknown_candidate", "recoverable": True}
        if evidence_level == "single_seed":
            candidate["status"] = "promising"
            candidate["claim_status"] = "not_claimable"
        else:
            candidate["status"] = "kept"
            candidate["claim_status"] = "claimable"
        candidate["updated_at"] = _utc_now()
        self._write(data)
        self.events.append("frontier.candidate_promoted", {"idea_id": idea_id, "evidence_level": evidence_level, "status": candidate["status"]})
        return {"ok": True, "candidate": candidate}

    def propose_generated_candidate(self, *, source: str, title: str) -> dict[str, Any]:
        manifest = ManifestService(self.layout).read()
        autonomy = manifest.get("autonomy") if isinstance(manifest.get("autonomy"), dict) else {}
        autonomous = autonomy.get("mode") == "autonomous" and autonomy.get("autonomous_idea_improvement") is True
        if not autonomous:
            return {
                "ok": True,
                "status": "needs_user_decision",
                "created_running_trial": False,
                "candidate": {"source": source, "title": title},
            }
        candidate = self.add_candidate(f"AUTO{len(self.select(limit=9999)) + 1:04d}", score=0.0, source=source, title=title)
        return {"ok": True, "status": "candidate", "created_running_trial": False, "candidate": candidate}

    def check_novelty(self, *, idea_id: str, mechanism: str) -> dict[str, Any]:
        from .journal import JournalService

        normalized = mechanism.casefold().strip()
        similar: list[str] = []
        for record in JournalService(self.layout).list_negative_memory():
            lesson = str(record.get("lesson", "")).casefold().strip()
            if lesson and (lesson in normalized or normalized in lesson):
                similar.append(str(record.get("idea_id")))
        if similar:
            decision = "block_duplicate"
        else:
            decision = "allow"
        return {"ok": True, "idea_id": idea_id, "decision": decision, "similar_failed_ideas": similar}
