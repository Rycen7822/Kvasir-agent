from __future__ import annotations

from pathlib import Path

from codex_scientist.services.checkpoint import CheckpointService
from codex_scientist.services.event_store import EventStore
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.resume import ResumeService


def test_pack_delta_reads_events_after_checkpoint_id(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    checkpoint = CheckpointService(layout).create_checkpoint(
        phase="P3-2",
        completed=["checkpoint"],
        decisions=[],
        validation=[],
        next_action="append event",
        artifact_refs=[],
        risk_flags=[],
    )
    EventStore(layout).append("runner.collected", {"run_id": "R0001", "status": "completed"})

    delta = ResumeService(layout).pack_delta(since_checkpoint_id=checkpoint["checkpoint_id"], max_chars=4000)

    assert delta["ok"] is True
    assert delta["source_event_range"]["since_checkpoint_id"] == checkpoint["checkpoint_id"]
    assert delta["source_event_range"]["start_event_seq"] == checkpoint["event_seq"] + 1
    assert delta["source_event_range"]["end_event_seq"] == checkpoint["event_seq"] + 1
    assert delta["new_events_summary"] == [{"event_seq": 2, "event_type": "runner.collected"}]
    assert delta["changed_runs"] == ["R0001"]
    assert delta["next_recommended_call"]["tool"] == "cs_resume_brief"


def test_event_store_assigns_virtual_seq_to_legacy_events(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    layout.ensure_core_dirs()
    layout.event_log_path.write_text(
        '{"event_id":"legacy1","event_type":"legacy.created","payload":{}}\n',
        encoding="utf-8",
    )

    events = EventStore(layout).read_events()
    appended = EventStore(layout).append("new.created", {})

    assert events[0]["event_seq"] == 1
    assert appended["event_seq"] == 2
