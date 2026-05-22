from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.services.checkpoint import CheckpointService
from codex_scientist.services.event_store import EventStore
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.resume import ResumeService


def test_checkpoint_writes_event_latest_snapshot_and_redacts_secrets(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)

    payload = CheckpointService(layout).create_checkpoint(
        phase="P3-2",
        completed=["wrote checkpoint token=" + "supersecret"],
        decisions=["keep password=" + "hunter2"],
        validation=["pytest checkpoint"],
        next_action="resume from compact state",
        artifact_refs=[{"path": "artifacts/result.json", "sha256": "abc"}],
        risk_flags=["none"],
    )

    assert payload["ok"] is True
    assert payload["checkpoint_id"].startswith("CP")
    assert len(payload["sha256"]) == 64
    assert payload["event_seq"] == 1
    assert Path(payload["latest_path"]).exists()
    assert Path(payload["checkpoint_log_path"]).exists()

    rendered = Path(payload["latest_path"]).read_text(encoding="utf-8")
    assert "supersecret" not in rendered
    assert "hunter2" not in rendered
    assert "[REDACTED]" in rendered

    latest = json.loads(rendered)
    assert latest["checkpoint_id"] == payload["checkpoint_id"]
    assert latest["phase"] == "P3-2"
    assert latest["event_seq"] == 1
    assert latest["sha256"] == payload["sha256"]

    events = EventStore(layout).read_events()
    assert [event["event_seq"] for event in events] == [1]
    assert events[0]["event_type"] == "checkpoint.created"
    assert events[0]["payload"]["checkpoint_id"] == payload["checkpoint_id"]
    assert events[0]["payload"]["artifact_refs"] == [{"path": "artifacts/result.json", "sha256": "abc"}]
    assert events[0]["payload"]["risk_flags"] == ["none"]


def test_checkpoint_same_payload_is_idempotent(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    service = CheckpointService(layout)
    first = service.create_checkpoint(phase="P3-7", completed=["same"], validation=["pytest"], next_action="continue")
    second = service.create_checkpoint(phase="P3-7", completed=["same"], validation=["pytest"], next_action="continue")

    assert second["checkpoint_id"] == first["checkpoint_id"]
    assert second["event_seq"] == first["event_seq"]
    assert second["reused"] is True
    assert len(EventStore(layout).read_events()) == 1
    assert len(service.list_checkpoints()) == 1


def test_pack_delta_surfaces_checkpoint_artifacts_and_risks(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    service = CheckpointService(layout)
    first = service.create_checkpoint(phase="before", completed=["start"], next_action="continue")
    service.create_checkpoint(
        phase="after",
        completed=["wrote artifact"],
        artifact_refs=["artifacts/formal_metric.txt"],
        risk_flags=["needs_log_digest_followup"],
        next_action="resume from checkpoint",
    )

    delta = ResumeService(layout).pack_delta(since_event_seq=first["event_seq"])

    assert delta["changed_artifacts"] == ["artifacts/formal_metric.txt"]
    assert delta["changed_risks"] == ["needs_log_digest_followup"]
