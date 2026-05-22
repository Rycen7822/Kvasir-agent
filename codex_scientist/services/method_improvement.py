from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .journal import JournalService
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _stable_score(seed: str, *, low: float = 0.35, high: float = 0.95) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    raw = int(digest[:8], 16) / 0xFFFFFFFF
    return round(low + (high - low) * raw, 4)


class MethodImprovementService:
    """Quest-scoped method improvement, novelty, and claim gates."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def _quest(self, quest_id: str):
        return self.layout.ensure_quest_layout(quest_id)

    def scoreboard_path(self, quest_id: str) -> Path:
        return self._quest(quest_id).quest_root / "method_memory" / "scoreboard" / "scoreboard.json"

    def frontier_path(self, quest_id: str) -> Path:
        return self._quest(quest_id).quest_root / "method_memory" / "frontier" / "frontier.json"

    def claim_gate_path(self, quest_id: str, claim_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(claim_id or "claim")) or "claim"
        return self._quest(quest_id).quest_root / "artifacts" / "decisions" / f"claim_gate_{safe}.json"

    def _analysis_slice_statuses(self, quest_id: str) -> dict[str, dict[str, Any]]:
        quest_root = self._quest(quest_id).quest_root
        campaigns_root = quest_root / ".cs" / "analysis_campaigns"
        statuses: dict[str, dict[str, Any]] = {}
        if not campaigns_root.exists():
            return statuses
        for path in sorted(campaigns_root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            campaign_id = str(payload.get("campaign_id") or path.stem).strip() or path.stem
            for item in payload.get("slices") or []:
                if not isinstance(item, dict):
                    continue
                slice_id = str(item.get("slice_id") or "").strip()
                if not slice_id:
                    continue
                statuses[slice_id] = {
                    "campaign_id": campaign_id,
                    "status": str(item.get("status") or "").strip().lower(),
                    "manifest_path": str(path),
                }
        return statuses

    @staticmethod
    def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else dict(default)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def score_novelty_contract(self, contract: dict[str, Any]) -> dict[str, float]:
        mechanism = str(contract.get("mechanism") or "").strip().casefold()
        related = "|".join(sorted(str(item).strip().casefold() for item in contract.get("related_work_refs") or [] if str(item).strip()))
        difference = str(contract.get("expected_difference") or "").strip().casefold()
        risks = "|".join(sorted(str(item).strip().casefold() for item in contract.get("risk_notes") or [] if str(item).strip()))
        base = f"{mechanism}\n{related}\n{difference}\n{risks}"
        evidence = min(1.0, 0.45 + 0.18 * len([item for item in contract.get("related_work_refs") or [] if str(item).strip()]))
        risk_penalty = min(0.35, 0.08 * len([item for item in contract.get("risk_notes") or [] if str(item).strip()]))
        return {
            "novelty": _stable_score("novelty:" + base),
            "feasibility": round(max(0.0, _stable_score("feasibility:" + base, low=0.45, high=0.9) - risk_penalty), 4),
            "evidence": round(evidence, 4),
            "risk": round(max(0.0, 1.0 - risk_penalty), 4),
            "diversity": _stable_score("diversity:" + base),
        }

    def validate_novelty_contract(self, contract: Any) -> dict[str, Any]:
        if not isinstance(contract, dict):
            return {
                "ok": False,
                "error": "novelty_contract is required",
                "error_type": "missing_novelty_contract",
                "recoverable": True,
                "required_fields": ["novelty_contract", "mechanism", "related_work_refs", "expected_difference"],
            }
        if not str(contract.get("mechanism") or "").strip():
            return {"ok": False, "error": "novelty_contract.mechanism is required", "error_type": "missing_mechanism", "recoverable": True}
        related = [str(item).strip() for item in contract.get("related_work_refs") or [] if str(item).strip()]
        if not related:
            return {"ok": False, "error": "novelty_contract.related_work_refs must not be empty", "error_type": "missing_related_work_refs", "recoverable": True}
        if not str(contract.get("expected_difference") or "").strip():
            return {"ok": False, "error": "novelty_contract.expected_difference is required", "error_type": "missing_expected_difference", "recoverable": True}
        normalized = dict(contract)
        normalized["related_work_refs"] = related
        normalized["selection_scores"] = self.score_novelty_contract(normalized)
        return {"ok": True, "novelty_contract": normalized}

    def duplicate_check(self, *, quest_id: str, mechanism: str) -> dict[str, Any]:
        normalized = str(mechanism or "").casefold().strip()
        similar: list[str] = []
        for record in JournalService(self.layout).list_negative_memory(quest_id=quest_id):
            lesson = str(record.get("lesson") or "").casefold().strip()
            failed_mechanism = str(record.get("mechanism") or "").casefold().strip()
            if normalized and ((failed_mechanism and (failed_mechanism in normalized or normalized in failed_mechanism)) or (lesson and (lesson in normalized or normalized in lesson))):
                similar.append(str(record.get("idea_id") or ""))
        return {"ok": True, "decision": "block_duplicate" if similar else "allow", "similar_failed_ideas": [item for item in similar if item]}

    def record_negative_result(self, *, quest_id: str, trial_id: str, idea_id: str, failure_reason: str, lesson: str, mechanism: str = "") -> dict[str, Any]:
        record = JournalService(self.layout).record_negative_result(
            trial_id=trial_id,
            idea_id=idea_id,
            failure_reason=failure_reason,
            lesson=lesson,
            quest_id=quest_id,
            mechanism=mechanism,
        )
        return {"ok": True, "record": record, "negative_memory_path": record.get("quest_path")}

    def update_scoreboard(self, *, quest_id: str, idea_id: str, outcome: str, metric_delta: float = 0.0, lesson: str = "", mechanism: str = "") -> dict[str, Any]:
        path = self.scoreboard_path(quest_id)
        scoreboard = self._read_json(path, {"schema_version": 1, "quest_id": quest_id, "ideas": {}, "updated_at": None})
        ideas = scoreboard.setdefault("ideas", {})
        ideas[idea_id] = {
            "idea_id": idea_id,
            "outcome": outcome,
            "metric_delta": float(metric_delta),
            "lesson": lesson,
            "mechanism": mechanism,
            "updated_at": _utc_now(),
        }
        scoreboard["updated_at"] = _utc_now()
        self._write_json(path, scoreboard)
        recorded_negative = str(outcome).lower() in {"negative", "failed", "regressed", "reverted"}
        negative = None
        if recorded_negative:
            negative = self.record_negative_result(
                quest_id=quest_id,
                trial_id=f"scoreboard:{idea_id}",
                idea_id=idea_id,
                failure_reason=str(outcome),
                lesson=lesson or mechanism or "negative method outcome",
                mechanism=mechanism,
            )
        frontier = self.update_frontier(quest_id=quest_id)
        self.events.append("method.scoreboard_updated", {"quest_id": quest_id, "idea_id": idea_id, "outcome": outcome})
        return {
            "ok": True,
            "scoreboard": scoreboard,
            "scoreboard_path": str(path),
            "recorded_negative_memory": recorded_negative,
            "negative_memory": negative,
            "frontier": frontier.get("frontier"),
        }

    def update_frontier(self, *, quest_id: str) -> dict[str, Any]:
        scoreboard = self._read_json(self.scoreboard_path(quest_id), {"ideas": {}})
        candidates = []
        blocked = []
        for idea in (scoreboard.get("ideas") or {}).values():
            if not isinstance(idea, dict):
                continue
            item = {
                "idea_id": idea.get("idea_id"),
                "score": round(0.5 + float(idea.get("metric_delta") or 0.0), 4),
                "outcome": idea.get("outcome"),
                "blocked_by_evidence": str(idea.get("outcome") or "").lower() in {"negative", "failed", "regressed", "reverted"},
            }
            if item["blocked_by_evidence"]:
                blocked.append(item)
            else:
                candidates.append(item)
        candidates.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("idea_id") or "")))
        frontier = {
            "schema_version": 1,
            "quest_id": quest_id,
            "candidate_ranking": candidates,
            "blocked_by_evidence": blocked,
            "diversity_gaps": ["need_non_duplicate_mechanism"] if blocked else [],
            "updated_at": _utc_now(),
        }
        path = self.frontier_path(quest_id)
        self._write_json(path, frontier)
        return {"ok": True, "frontier": frontier, "frontier_path": str(path)}

    def select_next_idea(self, *, quest_id: str) -> dict[str, Any]:
        frontier = self.update_frontier(quest_id=quest_id)["frontier"]
        ranking = list(frontier.get("candidate_ranking") or [])
        selected = ranking[0] if ranking else None
        return {"ok": True, "quest_id": quest_id, "next_idea": selected, "frontier": frontier}

    def claim_gate(
        self,
        *,
        quest_id: str,
        claim_id: str,
        claim_text: str,
        baseline_id: str | None,
        metric_contract: str | None,
        evidence_paths: list[Any] | None,
        analysis_slice_ids: list[Any] | None,
        seed_count: int,
    ) -> dict[str, Any]:
        blockers: list[str] = []
        if not baseline_id:
            blockers.append("baseline_missing")
        if not metric_contract:
            blockers.append("metric_contract_missing")
        resolved_paths: list[str] = []
        for value in evidence_paths or []:
            path = Path(str(value)).expanduser()
            if not path.is_absolute():
                path = self._quest(quest_id).quest_root / path
            if path.exists():
                resolved_paths.append(str(path))
        if not resolved_paths:
            blockers.append("evidence_path_missing")
        slice_ids = [str(item).strip() for item in analysis_slice_ids or [] if str(item).strip()]
        if not slice_ids:
            blockers.append("analysis_slice_missing")
        else:
            slice_statuses = self._analysis_slice_statuses(quest_id)
            for slice_id in slice_ids:
                status = slice_statuses.get(slice_id)
                if status is None:
                    blockers.append(f"analysis_slice_not_found:{slice_id}")
                    continue
                if status.get("status") not in {"completed", "accepted"}:
                    blockers.append(f"analysis_slice_not_completed:{slice_id}")
        if int(seed_count or 0) < 2:
            blockers.append("insufficient_seed_count")
        gate = {
            "claim_id": claim_id,
            "claim_text": claim_text,
            "quest_id": quest_id,
            "claimable": not blockers,
            "blocking_reasons": blockers,
            "baseline_id": baseline_id,
            "metric_contract": metric_contract,
            "evidence_paths": resolved_paths,
            "analysis_slice_ids": slice_ids,
            "seed_count": int(seed_count or 0),
            "updated_at": _utc_now(),
        }
        path = self.claim_gate_path(quest_id, claim_id)
        self._write_json(path, gate)
        payload = {"ok": not blockers, "claim_gate": gate, "claim_gate_path": str(path)}
        if blockers:
            payload.update({
                "error": "Claim gate blocked by missing or incomplete evidence",
                "error_type": "claim_gate_blocked",
                "recoverable": True,
                "blocking_reasons": blockers,
                "retry_template": {
                    "name": "cs_claim_gate",
                    "required_before_retry": [
                        "confirmed baseline_id or explicit waiver",
                        "metric_contract",
                        "existing evidence_paths",
                        "completed analysis_slice_ids from cs_record_analysis_slice",
                        "seed_count >= 2",
                    ],
                },
                "suggested_next_action": "Complete and record the referenced analysis slices, verify evidence paths exist, then retry cs_claim_gate.",
            })
        return payload
