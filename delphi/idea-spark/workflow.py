"""Parent-owned room checkpoints; native hosts still own agent execution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .store import IdeaSparkStore, canonical_json, with_retry
except ImportError:  # source-root script execution
    from store import IdeaSparkStore, canonical_json, with_retry


OPEN_DISCUSSION = "open_discussion"
DEEP_EXPLORATION = "deep_exploration"
WORKFLOW_MODES = (OPEN_DISCUSSION, DEEP_EXPLORATION)
TERMINAL_STATUSES = {"gated", "completed", "stopped"}


def workflow_mode(metadata: dict[str, Any]) -> str:
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a JSON object")
    mode = metadata.get("workflow_mode", OPEN_DISCUSSION)
    if not isinstance(mode, str) or mode not in WORKFLOW_MODES:
        raise ValueError("workflow_mode must be open_discussion or deep_exploration")
    return mode


def workflow_summary(metadata: dict[str, Any], status: str) -> dict[str, Any]:
    mode = workflow_mode(metadata)
    state = metadata.get("workflow_state", {})
    if not isinstance(state, dict):
        raise ValueError("workflow_state must be a JSON object")
    return {
        "workflow_mode": mode,
        "workflow_state": state,
        "is_terminal": status in TERMINAL_STATUSES,
        "final_artifact_id": state.get("final_artifact_id"),
    }


def _artifact(conn, room_id: str, artifact_id: str, expected_type: str | None = None):
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise ValueError("artifact references must be nonempty strings")
    row = conn.execute(
        "select * from artifacts where room_id = ? and artifact_id = ?",
        (room_id, artifact_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"artifact is not registered in this room: {artifact_id}")
    if expected_type and row["artifact_type"] != expected_type:
        raise ValueError(f"{artifact_id} must be a {expected_type}")
    return row


def save_checkpoint(room_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Merge an explicit parent decision and room status in one transaction.

    Retrying the same payload is safe. Counts are values supplied by the parent,
    never increments caused by a collection or checkpoint retry.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    for key in ("workflow_mode", "workflow_state", "metadata", "room_id"):
        if key in payload:
            raise ValueError(f"{key} cannot be changed here; pass checkpoint fields directly")
    patch = {key: value for key, value in payload.items() if key != "status"}
    for key in ("phase", "next_action", "candidate_label", "stop_reason"):
        value = patch.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{key} must be a string or null")
    for key in ("next_inputs", "pending_receipts"):
        if key in patch and (
            not isinstance(patch[key], list)
            or any(not isinstance(value, str) or not value.strip() for value in patch[key])
        ):
            raise ValueError(f"{key} must be a list of nonempty strings")
    if "revision_count" in patch and (
        type(patch["revision_count"]) is not int or patch["revision_count"] < 0
    ):
        raise ValueError("revision_count must be a nonnegative integer")
    store = IdeaSparkStore()
    store.initialize()

    def run():
        with store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            room = conn.execute("select * from rooms where room_id = ?", (room_id,)).fetchone()
            if room is None:
                raise ValueError("unknown room_id")
            metadata = json.loads(room["metadata_json"])
            summary = workflow_summary(metadata, room["status"])
            mode = summary["workflow_mode"]
            state = {**summary["workflow_state"], **patch}
            status = payload.get("status", room["status"])
            if mode == OPEN_DISCUSSION:
                if status != room["status"]:
                    raise ValueError("open_discussion closes through gate_record, not workflow checkpoint")
            elif not isinstance(status, str) or status not in {"open", "completed", "stopped"}:
                raise ValueError("deep_exploration status must be open, completed or stopped")
            if mode == DEEP_EXPLORATION and status in {"completed", "stopped"}:
                if "phase" not in patch:
                    state["phase"] = status
                state["next_action"] = None
            if room["status"] in {"completed", "stopped"} and status != room["status"]:
                raise ValueError("terminal status cannot be changed; start another room")

            for key, artifact_type in (
                ("active_gap_artifact_id", "GapAnalysis"),
                ("active_candidate_artifact_id", "IdeaCard"),
                ("final_artifact_id", None),
            ):
                if state.get(key) is not None:
                    _artifact(conn, room_id, state[key], artifact_type)
            for artifact_id in state.get("next_inputs", []):
                _artifact(conn, room_id, artifact_id)
            if status == "completed":
                if not state.get("final_artifact_id"):
                    raise ValueError("completed requires final_artifact_id for a registered ResearchProposal file")
                final = _artifact(conn, room_id, state.get("final_artifact_id"), "ResearchProposal")
                if not final["file_path"]:
                    raise ValueError("completed requires a ResearchProposal file")
            if status == "stopped" and not str(state.get("stop_reason") or "").strip():
                raise ValueError("stopped requires a stop_reason")
            if status in {"completed", "stopped"} and state.get("final_artifact_id"):
                final = _artifact(conn, room_id, state["final_artifact_id"])
                path = Path(final["file_path"]) if final["file_path"] else None
                if path is None or not path.is_file() or path.stat().st_size == 0:
                    raise ValueError("final artifact file is missing or empty")

            updated = {**metadata, "workflow_mode": mode, "workflow_state": state}
            unchanged = updated == metadata and status == room["status"]
            if not unchanged:
                conn.execute(
                    "update rooms set metadata_json = ?, status = ? where room_id = ?",
                    (canonical_json(updated), status, room_id),
                )
        return {
            "success": True,
            "room_id": room_id,
            "status": status,
            "idempotent": unchanged,
            **workflow_summary(updated, status),
        }

    return with_retry(run)
