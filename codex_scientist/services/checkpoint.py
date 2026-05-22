from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from codex_scientist.runtime.redaction import redact_payload

from .event_store import EventStore
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


class CheckpointService:
    """Persist compact recovery checkpoints under project-local state."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.summaries_dir = layout.state_root / "summaries"
        self.checkpoint_log_path = self.summaries_dir / "checkpoints.jsonl"
        self.latest_path = self.summaries_dir / "latest_checkpoint.json"

    def _next_checkpoint_id(self) -> str:
        return "CP" + datetime.now(UTC).strftime("%Y%m%d%H%M%S") + uuid4().hex[:6]

    def _append_checkpoint_log(self, checkpoint: dict[str, Any]) -> None:
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        with self.checkpoint_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")

    def list_checkpoints(self) -> list[dict[str, Any]]:
        if not self.checkpoint_log_path.exists():
            return []
        checkpoints: list[dict[str, Any]] = []
        for line in self.checkpoint_log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            loaded = json.loads(line)
            if isinstance(loaded, dict):
                checkpoints.append(loaded)
        return checkpoints

    def latest_checkpoint(self) -> dict[str, Any] | None:
        if not self.latest_path.exists():
            return None
        loaded = json.loads(self.latest_path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None

    def find_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        for checkpoint in reversed(self.list_checkpoints()):
            if checkpoint.get("checkpoint_id") == checkpoint_id:
                return checkpoint
        return None

    def _response(self, checkpoint: dict[str, Any], *, reused: bool) -> dict[str, Any]:
        return {
            "ok": True,
            "checkpoint_id": checkpoint["checkpoint_id"],
            "event_seq": checkpoint["event_seq"],
            "sha256": checkpoint["sha256"],
            "latest_path": str(self.latest_path),
            "checkpoint_log_path": str(self.checkpoint_log_path),
            "checkpoint": checkpoint,
            "reused": reused,
            "source_refs": [{"path": str(self.latest_path), "kind": "latest_checkpoint"}],
        }

    def find_checkpoint_by_content_hash(self, content_hash: str) -> dict[str, Any] | None:
        for checkpoint in reversed(self.list_checkpoints()):
            if checkpoint.get("content_hash") == content_hash:
                return checkpoint
        return None

    def create_checkpoint(
        self,
        *,
        phase: str,
        completed: list[Any] | None = None,
        decisions: list[Any] | None = None,
        validation: list[Any] | None = None,
        next_action: str = "",
        artifact_refs: list[Any] | None = None,
        risk_flags: list[Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        body = redact_payload(
            {
                "phase": str(phase),
                "completed": list(completed or []),
                "decisions": list(decisions or []),
                "validation": list(validation or []),
                "next_action": str(next_action or ""),
                "artifact_refs": list(artifact_refs or []),
                "risk_flags": list(risk_flags or []),
            }
        )
        content_hash = _digest(body)
        event_idempotency_key = str(idempotency_key or f"checkpoint:{content_hash}")
        existing = self.find_checkpoint_by_content_hash(content_hash)
        if existing is not None:
            self.events.write_snapshot(existing, self.latest_path)
            return self._response(existing, reused=True)

        checkpoint_id = self._next_checkpoint_id()
        checkpoint = {
            "schema_version": 1,
            "checkpoint_id": checkpoint_id,
            "created_at": _utc_now(),
            **body,
            "content_hash": content_hash,
            "idempotency_key": event_idempotency_key,
        }
        event = self.events.append(
            "checkpoint.created",
            {
                "checkpoint_id": checkpoint_id,
                "phase": checkpoint["phase"],
                "next_action": checkpoint["next_action"],
                "artifact_refs": checkpoint["artifact_refs"],
                "risk_flags": checkpoint["risk_flags"],
                "content_hash": content_hash,
            },
            idempotency_key=event_idempotency_key,
        )
        existing_id = (event.get("payload") or {}).get("checkpoint_id")
        if existing_id and existing_id != checkpoint_id:
            existing = self.find_checkpoint(str(existing_id))
            if existing is not None:
                self.events.write_snapshot(existing, self.latest_path)
                return self._response(existing, reused=True)
        checkpoint["event_seq"] = event["event_seq"]
        checkpoint["sha256"] = _digest({key: value for key, value in checkpoint.items() if key != "sha256"})

        self.events.write_snapshot(checkpoint, self.latest_path)
        self._append_checkpoint_log(checkpoint)
        return self._response(checkpoint, reused=False)
