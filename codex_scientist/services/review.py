from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from deepscientist_native.redaction import redact_payload, redact_text

from .event_store import EventStore
from .project_state import ProjectLayout

ALLOWED_REVIEW_ACTIONS = [
    "read_manifest",
    "read_trial_summary",
    "read_metric",
    "read_artifact_paths",
    "write_review_artifact",
]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ReviewService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.reviews_dir = layout.state_root / "reviews"

    def create_review(
        self,
        *,
        claim_text: str,
        trial_ids: list[str],
        artifact_paths: list[str],
        verdict: str,
        notes: str,
    ) -> dict[str, Any]:
        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        review_id = f"review_{uuid4().hex[:12]}"
        review = {
            "review_id": review_id,
            "created_at": _utc_now(),
            "read_only": True,
            "allowed_actions": ALLOWED_REVIEW_ACTIONS,
            "claim_text": claim_text,
            "trial_ids": trial_ids,
            "artifact_paths": artifact_paths,
            "verdict": verdict,
            "notes": notes,
        }
        review = redact_payload(review)
        json_path = self.reviews_dir / f"{review_id}.json"
        markdown_path = self.reviews_dir / f"{review_id}.md"
        json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        markdown = (
            f"# Review {review_id}\n\n"
            f"verdict: {redact_text(verdict)}\n\n"
            f"claim: {redact_text(claim_text)}\n\n"
            f"trial_ids: {', '.join(trial_ids)}\n\n"
            f"artifact_paths: {', '.join(artifact_paths)}\n\n"
            f"notes: {redact_text(notes)}\n"
        )
        markdown_path.write_text(markdown, encoding="utf-8")
        self.events.append("review.created", {"review_id": review_id, "verdict": verdict})
        return {"ok": True, "review": review, "json_path": str(json_path), "markdown_path": str(markdown_path)}

    def status(self) -> dict[str, Any]:
        if not self.reviews_dir.exists():
            return {"ok": True, "count": 0, "reviews": [], "path": str(self.reviews_dir)}
        reviews: list[dict[str, Any]] = []
        for path in sorted(self.reviews_dir.glob("*.json")):
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(loaded, dict):
                reviews.append({"review_id": loaded.get("review_id"), "verdict": loaded.get("verdict"), "path": str(path)})
        return {"ok": True, "count": len(reviews), "reviews": reviews, "path": str(self.reviews_dir)}
