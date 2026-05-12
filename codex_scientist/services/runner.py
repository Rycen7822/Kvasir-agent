from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_scientist.runtime.redaction import redact_text

from .event_store import EventStore
from .project_state import ProjectLayout

TERMINAL_STATUSES = {"completed", "failed_metric", "failed_artifact", "failed_readonly", "failed_timeout", "failed_other", "cancelled", "stuck"}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class RunnerService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.runs_dir = layout.state_root / "runs"

    def _next_run_id(self) -> str:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        existing = [path.name for path in self.runs_dir.glob("R[0-9][0-9][0-9][0-9]") if path.is_dir()]
        number = max([int(name[1:]) for name in existing] or [0]) + 1
        return f"R{number:04d}"

    def _run_path(self, run_id: str) -> Path:
        return self.runs_dir / run_id / "runner.json"

    def _write(self, run: dict[str, Any]) -> None:
        path = self._run_path(run["run_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def get(self, run_id: str) -> dict[str, Any]:
        return json.loads(self._run_path(run_id).read_text(encoding="utf-8"))

    def list_runs(self) -> list[dict[str, Any]]:
        if not self.runs_dir.exists():
            return []
        return [self.get(path.name) for path in sorted(self.runs_dir.glob("R[0-9][0-9][0-9][0-9]")) if path.is_dir()]

    def start(self, *, command: str, job_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
        run_id = self._next_run_id()
        run_dir = self.runs_dir / run_id
        log_path = run_dir / "run.log"
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path.touch()
        now = _utc_now()
        status = "dry_run" if dry_run else "running"
        run = {
            "run_id": run_id,
            "job_id": job_id,
            "command": command,
            "status": status,
            "terminal": False,
            "created_at": now,
            "updated_at": now,
            "heartbeat_at": now,
            "log_path": str(log_path),
            "exit_code": None,
        }
        self._write(run)
        self.events.append("runner.started", {"run_id": run_id, "job_id": job_id, "status": status})
        return {"ok": True, "run": run}

    def update_status(self, run_id: str, status: str, *, exit_code: int | None = None) -> dict[str, Any]:
        run = self.get(run_id)
        run["status"] = status
        run["terminal"] = status in TERMINAL_STATUSES
        run["exit_code"] = exit_code
        run["updated_at"] = _utc_now()
        self._write(run)
        self.events.append("runner.updated", {"run_id": run_id, "status": status, "exit_code": exit_code})
        return {"ok": True, "run": run}

    def collect(self, run_id: str, *, exit_code: int) -> dict[str, Any]:
        status = "completed" if int(exit_code) == 0 else "failed_other"
        return self.update_status(run_id, status, exit_code=exit_code)

    def tail(self, run_id: str, *, limit: int = 80) -> dict[str, Any]:
        run = self.get(run_id)
        lines = Path(run["log_path"]).read_text(encoding="utf-8", errors="replace").splitlines()
        bounded = lines[-max(int(limit), 0):] if limit else []
        return {"ok": True, "run_id": run_id, "lines": [redact_text(line) for line in bounded]}
