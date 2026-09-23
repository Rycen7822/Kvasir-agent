from __future__ import annotations

import fcntl
import json
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .project_state import ProjectLayout

SCHEMA_VERSION = 1
_PROCESS_LOCKS: dict[Path, threading.Lock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _safe_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _process_lock_for(path: Path) -> threading.Lock:
    resolved = path.resolve()
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(resolved)
        if lock is None:
            lock = threading.Lock()
            _PROCESS_LOCKS[resolved] = lock
        return lock


class EventStore:
    """Small append-only JSONL event store plus atomic snapshot helper."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.path = layout.event_log_path
        self.lock_path = self.path.with_suffix(".lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.layout.ensure_core_dirs()
        process_lock = _process_lock_for(self.lock_path)
        with process_lock:
            with self.lock_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def append(self, event_type: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        with self._locked():
            events = self._read_events_unlocked(quarantine=True)
            if idempotency_key:
                for event in events:
                    if event.get("idempotency_key") == idempotency_key:
                        return event
            event = {
                "schema_version": SCHEMA_VERSION,
                "event_seq": self._next_event_seq_unlocked(events),
                "event_id": uuid4().hex,
                "event_type": str(event_type),
                "created_at": utc_now(),
                "payload": dict(payload),
            }
            if idempotency_key:
                event["idempotency_key"] = str(idempotency_key)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            return event

    def next_event_seq(self) -> int:
        if not self.path.exists():
            return 1
        with self._locked():
            return self._next_event_seq_unlocked(self._read_events_unlocked(quarantine=True))

    @staticmethod
    def _next_event_seq_unlocked(events: list[dict[str, Any]]) -> int:
        return max([int(event.get("event_seq") or 0) for event in events] or [0]) + 1

    def read_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self._locked():
            return self._read_events_unlocked(quarantine=True)

    def _read_events_unlocked(self, *, quarantine: bool) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        valid_lines: list[str] = []
        corrupt_lines: list[tuple[int, str]] = []
        for index, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                loaded = json.loads(line)
            except json.JSONDecodeError:
                corrupt_lines.append((index, line))
                continue
            if isinstance(loaded, dict):
                loaded.setdefault("event_seq", index)
                events.append(loaded)
                valid_lines.append(json.dumps(loaded, ensure_ascii=False, sort_keys=True))
            else:
                corrupt_lines.append((index, line))
        if corrupt_lines and quarantine:
            corrupt_dir = self.layout.events_dir / "corrupt"
            corrupt_dir.mkdir(parents=True, exist_ok=True)
            timestamp = _safe_timestamp()
            for line_number, line in corrupt_lines:
                quarantine_path = corrupt_dir / f"events.jsonl.line{line_number}.corrupt.{timestamp}"
                quarantine_path.write_text(line + "\n", encoding="utf-8")
            tmp = self.path.with_name(f"{self.path.name}.{uuid4().hex}.tmp")
            tmp.write_text("\n".join(valid_lines) + ("\n" if valid_lines else ""), encoding="utf-8")
            tmp.replace(self.path)
        return events

    def read_events_since(self, event_seq: int | None) -> list[dict[str, Any]]:
        since = int(event_seq or 0)
        return [event for event in self.read_events() if int(event.get("event_seq") or 0) > since]

    def write_snapshot(self, snapshot: dict[str, Any], path: Path | None = None) -> None:
        target = path or self.layout.project_state_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
        tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(target)

    def read_snapshot(self, default: dict[str, Any] | None = None, path: Path | None = None) -> dict[str, Any]:
        target = path or self.layout.project_state_path
        if not target.exists():
            return dict(default or {})
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            quarantine = target.with_name(f"{target.name}.corrupt.{_safe_timestamp()}")
            target.replace(quarantine)
            return dict(default or {})
        if not isinstance(loaded, dict):
            return dict(default or {})
        return loaded
