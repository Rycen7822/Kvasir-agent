from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ClaimEvidenceService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.claims_dir = layout.state_root / "claims"
        self.claims_path = self.claims_dir / "claims.jsonl"
        self.matrix_path = self.claims_dir / "evidence_matrix.md"

    def _read_claims(self) -> list[dict[str, Any]]:
        if not self.claims_path.exists():
            return []
        return [json.loads(line) for line in self.claims_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _write_claims(self, claims: list[dict[str, Any]]) -> None:
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self.claims_path.write_text("".join(json.dumps(claim, ensure_ascii=False, sort_keys=True) + "\n" for claim in claims), encoding="utf-8")

    @staticmethod
    def _is_result_claim(claim: dict[str, Any]) -> bool:
        return bool(claim.get("supporting_trial_ids")) and bool(claim.get("metric_values")) and bool(claim.get("artifact_paths")) and claim.get("reviewer_verdict") == "pass"

    def _write_matrix(self, claims: list[dict[str, Any]]) -> None:
        lines = ["# Claim Evidence Matrix", "", "| claim_id | status | supporting_trials | metrics | limitations | reviewer |", "|---|---|---|---|---|---|"]
        for claim in claims:
            lines.append(
                "| {claim_id} | {status} | {trials} | {metrics} | {limits} | {reviewer} |".format(
                    claim_id=claim.get("claim_id", ""),
                    status=claim.get("status", ""),
                    trials=",".join(claim.get("supporting_trial_ids") or []),
                    metrics=json.dumps(claim.get("metric_values") or {}, ensure_ascii=False, sort_keys=True),
                    limits=",".join(claim.get("limitations") or []),
                    reviewer=claim.get("reviewer_verdict") or "",
                )
            )
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self.matrix_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def upsert_claim(
        self,
        *,
        claim_id: str,
        text: str,
        supporting_trial_ids: list[str] | None = None,
        metric_values: dict[str, float] | None = None,
        artifact_paths: list[str] | None = None,
        limitations: list[str] | None = None,
        contradictory_trial_ids: list[str] | None = None,
        reviewer_verdict: str | None = None,
    ) -> dict[str, Any]:
        claim = {
            "claim_id": claim_id,
            "text": text,
            "supporting_trial_ids": supporting_trial_ids or [],
            "metric_values": metric_values or {},
            "artifact_paths": artifact_paths or [],
            "limitations": limitations or [],
            "contradictory_trial_ids": contradictory_trial_ids or [],
            "reviewer_verdict": reviewer_verdict,
            "updated_at": _utc_now(),
        }
        if self._is_result_claim(claim):
            claim["status"] = "result_claim"
            claim["included_in_results"] = True
        else:
            claim["status"] = "hypothesis"
            claim["included_in_results"] = False
        claims = [existing for existing in self._read_claims() if existing.get("claim_id") != claim_id]
        claims.append(claim)
        self._write_claims(claims)
        self._write_matrix(claims)
        self.events.append("claim.upserted", {"claim_id": claim_id, "status": claim["status"]})
        return {"ok": True, "claim": claim, "claims_path": str(self.claims_path), "matrix_path": str(self.matrix_path)}
