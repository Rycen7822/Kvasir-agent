"""Minimal v3 project state. Constructors and reads never create or repair files."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import math
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml

from .evidence_contracts import EvidenceError, read_json


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def within(root: Path, value: str, *, exists=False):
    path = Path(value)
    if ".." in path.parts or "\\" in value:
        raise EvidenceError("invalid_path", "Parent traversal is not allowed.")
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise EvidenceError("invalid_path", "Path escapes its owning directory.")
    if exists and not target.exists():
        raise EvidenceError("invalid_path", "Referenced path does not exist.")
    return target


def process_identity(pid):
    """Linux PID + start tick + boot identity protects against PID reuse."""
    try:
        text = Path(f"/proc/{int(pid)}/stat").read_text()
        fields = text[text.rfind(")") + 2:].split()
        if fields[0] == "Z":
            return None
        return {"pid": int(pid), "start": fields[19],
                "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
    except (OSError, ValueError, IndexError, TypeError):
        return None


def alive(identity):
    return bool(isinstance(identity, dict) and identity and process_identity(identity.get("pid")) == identity)


class ResearchState:
    def __init__(self, project):
        if not isinstance(project, str) or not Path(project).is_absolute():
            raise EvidenceError("invalid_project", "project must be an absolute directory.")
        self.project = Path(project).resolve()
        if not self.project.is_dir():
            raise EvidenceError("invalid_project", "Project directory does not exist.")
        self.root = self.project / "Kvasir-agent"
        self.manifest = self.path("research.yaml")

    def path(self, relative):
        raw = Path(relative)
        if raw.is_absolute() or ".." in raw.parts:
            raise EvidenceError("invalid_path", "Invalid state path.")
        target = self.root / raw
        for p in (target, *target.parents):
            if p == self.project:
                break
            if p.is_symlink():
                raise EvidenceError("invalid_path", "State paths cannot be symlinks.")
        return target

    def read_manifest(self, *, pending_ok=False):
        if not pending_ok and self.path("migrations/pending.json").exists():
            raise EvidenceError("migration_pending", "Project migration is incomplete.")
        if not self.manifest.exists():
            if self.path("quests").exists() or self.path("quest.yaml").exists():
                raise EvidenceError("migration_required", "Legacy project format.")
            raise EvidenceError("not_initialized", "Project state is unavailable.")
        try:
            if self.manifest.stat().st_size > 2_000_000:
                raise ValueError("oversized")
            m = yaml.safe_load(self.manifest.read_text())
            if not isinstance(m, dict):
                raise ValueError("not object")
        except (ValueError, yaml.YAMLError, UnicodeError) as exc:
            raise EvidenceError("corrupt_manifest", "Project manifest is invalid.") from exc
        if m.get("schema_version") != 3:
            kind = "future_schema" if isinstance(m.get("schema_version"), int) and m["schema_version"] > 3 else "migration_required"
            raise EvidenceError(kind, "Unsupported project format.")
        if (not isinstance(m.get("project_id"), str)
                or not re.fullmatch(r"[a-f0-9]{32}", m["project_id"]) or m.get("layout_version") != 3):
            raise EvidenceError("corrupt_manifest", "Project identity or layout is invalid.")
        try:
            datetime.fromisoformat(m["created_at"])
        except (KeyError, ValueError, TypeError):
            raise EvidenceError("corrupt_manifest", "Project creation timestamp is invalid.") from None
        return m

    @contextmanager
    def locked(self, *, create=False):
        if create:
            self.path("events").mkdir(parents=True, exist_ok=True)
        elif not self.root.is_dir():
            raise EvidenceError("not_initialized", "Project state is unavailable.")
        lock_path = self.path("events/write.lock")
        with lock_path.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def write(self, relative, data):
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            with tmp.open("x") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(target)
            fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            tmp.unlink(missing_ok=True)
        return target

    def events(self):
        path = self.path("events/events.jsonl")
        if not path.exists():
            return [], []
        events, bad = [], []
        with path.open("rb") as f:
            for number, line in enumerate(f, 1):
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict) or not isinstance(event.get("event_seq"), int):
                        raise ValueError("invalid event")
                    events.append(event)
                except (ValueError, UnicodeError):
                    bad.append(number)
        return events, bad

    def event(self, kind, payload, *, key):
        # Caller owns the project lock. A bad journal requires explicit repair.
        events, bad = self.events()
        if bad:
            raise EvidenceError("corrupt_events", "Event journal contains invalid lines.")
        if any(e.get("idempotency_key") == key for e in events):
            return
        item = {"event_seq": max((e["event_seq"] for e in events), default=0) + 1,
                "event_type": kind, "created_at": now(), "payload": payload, "idempotency_key": key}
        with self.path("events/events.jsonl").open("a") as f:
            f.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def initialize(self):
        if self.manifest.exists():
            m = self.read_manifest()
            return {"ok": True, "project_id": m["project_id"], "created": False,
                    "path": str(self.manifest)}
        if self.root.exists() and any(p.name not in {"events"} for p in self.root.iterdir()):
            if self.manifest.exists():
                return self.initialize()
            raise EvidenceError("migration_required", "Existing state requires explicit maintenance.")
        with self.locked(create=True):
            if self.manifest.exists():
                m = self.read_manifest()
                return {"ok": True, "project_id": m["project_id"], "created": False,
                        "path": str(self.manifest)}
            m = {"schema_version": 3, "layout_version": 3, "project_id": uuid4().hex, "created_at": now()}
            self.event("project.created", {"project_id": m["project_id"]}, key="project.created")
            self.write("research.yaml", m)
        return {"ok": True, "created": True, "project_id": m["project_id"], "path": str(self.manifest)}

    def read_run(self, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
            raise EvidenceError("invalid_run_id", "Invalid run identifier.")
        record = read_json(self.path(f"runs/{run_id}/run.json"))
        if not isinstance(record, dict) or record.get("run_id") != run_id:
            raise EvidenceError("corrupt_run", "Run record is invalid.")
        if record.get("status") not in {"starting", "running", "completed", "failed", "cancelled", "timed_out", "interrupted", "imported"}:
            raise EvidenceError("corrupt_run", "Run status is invalid.")
        if record.get("evidence_status") not in {"pending", "verified", "invalid", "unverified"}:
            raise EvidenceError("corrupt_run", "Run evidence status is invalid.")
        metric = record.get("metric")
        if metric is not None and (isinstance(metric, bool) or not isinstance(metric, (int, float)) or not math.isfinite(metric)):
            raise EvidenceError("corrupt_run", "Run metric is invalid.")
        return record

    def repair_events(self):
        self.read_manifest()
        with self.locked():
            events, bad = self.events()
            if bad:
                source = self.path("events/events.jsonl")
                backup = self.path(f"migrations/events-{uuid4().hex}.jsonl")
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(source.read_bytes())
                temp = source.with_suffix(".repair")
                temp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
                temp.replace(source)
            return {"ok": True, "repaired_lines": len(bad), "backup": str(backup) if bad else None}
