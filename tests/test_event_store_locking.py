from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from codex_scientist.services.event_store import EventStore
from codex_scientist.services.project_state import ProjectLayout


def test_event_store_concurrent_appends_are_sequential_and_idempotent(tmp_path):
    store = EventStore(ProjectLayout.from_project_root(tmp_path))

    def append(index: int) -> dict:
        return store.append("concurrent.event", {"index": index}, idempotency_key=f"key-{index % 10}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(append, range(40)))

    events = store.read_events()
    assert len(events) == 10
    assert [event["event_seq"] for event in events] == list(range(1, 11))
    assert len({event["event_id"] for event in results}) == 10
    assert {event["idempotency_key"] for event in events} == {f"key-{index}" for index in range(10)}


def test_event_store_quarantines_single_corrupt_jsonl_line(tmp_path):
    layout = ProjectLayout.from_project_root(tmp_path)
    store = EventStore(layout)
    first = store.append("first", {})
    second = store.append("second", {})
    lines = [json.dumps(first), "{broken", json.dumps(second)]
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    events = store.read_events()

    assert [event["event_type"] for event in events] == ["first", "second"]
    corrupt_files = list((layout.events_dir / "corrupt").glob("events.jsonl.line*.corrupt.*"))
    assert len(corrupt_files) == 1
    assert corrupt_files[0].read_text(encoding="utf-8") == "{broken\n"
    remaining_lines = store.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(remaining_lines) == 2
