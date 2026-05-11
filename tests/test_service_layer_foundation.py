from __future__ import annotations

import json
from pathlib import Path


def test_project_layout_uses_project_local_deepscientist_tree(tmp_path: Path):
    from codex_scientist.services.project_state import ProjectLayout

    layout = ProjectLayout.from_project_root(tmp_path)
    assert layout.project_root == tmp_path
    assert layout.state_root == tmp_path / "DeepScientist"
    assert layout.project_state_path == tmp_path / "DeepScientist" / "project_state.json"
    assert layout.event_log_path == tmp_path / "DeepScientist" / "events" / "events.jsonl"

    layout.ensure_core_dirs()
    assert layout.state_root.is_dir()
    assert layout.events_dir.is_dir()
    assert layout.runtime_dir.is_dir()


def test_event_store_appends_schema_versioned_jsonl(tmp_path: Path):
    from codex_scientist.services.event_store import EventStore
    from codex_scientist.services.project_state import ProjectLayout

    store = EventStore(ProjectLayout.from_project_root(tmp_path))
    first = store.append("quest.created", {"quest_id": "q1"})
    second = store.append("trial.updated", {"trial_id": "t1"})

    assert first["schema_version"] == 1
    assert first["event_type"] == "quest.created"
    assert first["event_id"] != second["event_id"]
    assert first["created_at"] <= second["created_at"]

    lines = store.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["event_type"] for line in lines] == ["quest.created", "trial.updated"]
    assert [event["event_type"] for event in store.read_events()] == ["quest.created", "trial.updated"]


def test_snapshot_write_is_atomic_and_corrupt_snapshot_is_quarantined(tmp_path: Path):
    from codex_scientist.services.event_store import EventStore
    from codex_scientist.services.project_state import ProjectLayout

    layout = ProjectLayout.from_project_root(tmp_path)
    store = EventStore(layout)

    store.write_snapshot({"status": "ok"})
    assert json.loads(layout.project_state_path.read_text(encoding="utf-8"))["status"] == "ok"
    assert not list(layout.state_root.glob("*.tmp"))

    layout.project_state_path.write_text("{broken", encoding="utf-8")
    result = store.read_snapshot(default={"status": "rebuilt"})

    assert result == {"status": "rebuilt"}
    corrupt_files = list(layout.state_root.glob("project_state.json.corrupt.*"))
    assert len(corrupt_files) == 1
    assert corrupt_files[0].read_text(encoding="utf-8") == "{broken"
