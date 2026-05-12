from __future__ import annotations

import hashlib
import json
import os
import shlex
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_scientist.runtime.redaction import redact_text

from .event_store import EventStore
from .project_state import ProjectLayout

TERMINAL_STATUSES = {"completed", "failed_metric", "failed_artifact", "failed_readonly", "failed_timeout", "failed_other", "failed_oom", "failed_transient", "cancelled", "stuck"}


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

    def _write_heartbeat(self, run: dict[str, Any]) -> None:
        heartbeat_path = Path(run["heartbeat_path"])
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        heartbeat_path.write_text(str(run["heartbeat_at"]) + "\n", encoding="utf-8")

    def get(self, run_id: str) -> dict[str, Any]:
        return json.loads(self._run_path(run_id).read_text(encoding="utf-8"))

    def list_runs(self) -> list[dict[str, Any]]:
        if not self.runs_dir.exists():
            return []
        return [self.get(path.name) for path in sorted(self.runs_dir.glob("R[0-9][0-9][0-9][0-9]")) if path.is_dir()]

    @staticmethod
    def is_process_alive(pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        proc_stat = Path(f"/proc/{pid}/stat")
        if proc_stat.exists():
            try:
                parts = proc_stat.read_text(encoding="utf-8", errors="replace").split()
                if len(parts) > 2 and parts[2] == "Z":
                    return False
            except OSError:
                return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @staticmethod
    def _poll_exit_code(pid: int | None) -> int | None:
        if not pid:
            return None
        try:
            waited_pid, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return None
        if waited_pid == 0:
            return None
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        if os.WIFSIGNALED(status):
            return -int(os.WTERMSIG(status))
        return None

    @staticmethod
    def _read_exit_code_file(run: dict[str, Any]) -> int | None:
        raw_path = run.get("exit_code_path")
        if not raw_path:
            return None
        path = Path(str(raw_path))
        if not path.exists():
            return None
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def start(self, *, command: str, job_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
        run_id = self._next_run_id()
        run_dir = self.runs_dir / run_id
        log_path = run_dir / "run.log"
        stderr_log_path = run_dir / "stderr.log"
        exit_code_path = run_dir / "exit_code.txt"
        heartbeat_path = run_dir / "heartbeat.txt"
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path.touch()
        stderr_log_path.touch()
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
            "heartbeat_path": str(heartbeat_path),
            "log_path": str(log_path),
            "stderr_log_path": str(stderr_log_path),
            "exit_code_path": str(exit_code_path),
            "exit_code": None,
            "pid": None,
            "pgid": None,
        }
        if not dry_run:
            wrapped_command = (
                f"{command}\n"
                "status=$?\n"
                f"printf '%s\\n' \"$status\" > {shlex.quote(str(exit_code_path))}\n"
                "exit \"$status\""
            )
            with log_path.open("ab", buffering=0) as stdout_handle, stderr_log_path.open("ab", buffering=0) as stderr_handle:
                process = subprocess.Popen(
                    wrapped_command,
                    cwd=str(self.layout.project_root),
                    shell=True,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    start_new_session=True,
                    close_fds=True,
                )
            run["pid"] = process.pid
            try:
                run["pgid"] = os.getpgid(process.pid)
            except ProcessLookupError:
                run["pgid"] = process.pid
        self._write_heartbeat(run)
        self._write(run)
        self.events.append("runner.started", {"run_id": run_id, "job_id": job_id, "status": status, "pid": run.get("pid")})
        return {"ok": True, "run": run}

    def heartbeat(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        run["heartbeat_at"] = _utc_now()
        run["updated_at"] = run["heartbeat_at"]
        run.setdefault("heartbeat_path", str(self.runs_dir / run_id / "heartbeat.txt"))
        self._write_heartbeat(run)
        self._write(run)
        self.events.append("runner.heartbeat", {"run_id": run_id, "heartbeat_at": run["heartbeat_at"]})
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

    def collect(self, run_id: str, *, exit_code: int | None = None) -> dict[str, Any]:
        run = self.get(run_id)
        if exit_code is None:
            exit_code = self._poll_exit_code(run.get("pid"))
        if exit_code is None:
            exit_code = self._read_exit_code_file(run)
        if exit_code is None:
            if self.is_process_alive(run.get("pid")):
                return {"ok": True, "run": run, "collected": False}
            status = "failed_other"
            result = self.update_status(run_id, status, exit_code=None)
            result["collected"] = True
            result["warning"] = "missing_exit_code_sentinel"
            return result
        status = "completed" if int(exit_code) == 0 else "failed_other"
        result = self.update_status(run_id, status, exit_code=exit_code)
        result["collected"] = True
        return result

    def cancel(self, run_id: str, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
        run = self.get(run_id)
        pid = run.get("pid")
        pgid = run.get("pgid") or pid
        if self.is_process_alive(pid):
            try:
                os.killpg(int(pgid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.time() + timeout_seconds
            while time.time() < deadline and self.is_process_alive(pid):
                self._poll_exit_code(pid)
                time.sleep(0.05)
            if self.is_process_alive(pid):
                try:
                    os.killpg(int(pgid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                deadline = time.time() + timeout_seconds
                while time.time() < deadline and self.is_process_alive(pid):
                    self._poll_exit_code(pid)
                    time.sleep(0.05)
        self._poll_exit_code(pid)
        return self.update_status(run_id, "cancelled", exit_code=-15)

    def tail(self, run_id: str, *, limit: int = 80) -> dict[str, Any]:
        run = self.get(run_id)
        lines = Path(run["log_path"]).read_text(encoding="utf-8", errors="replace").splitlines()
        bounded = lines[-max(int(limit), 0):] if limit else []
        return {"ok": True, "run_id": run_id, "lines": [redact_text(line) for line in bounded]}

    @staticmethod
    def _heartbeat_age_seconds(run: dict[str, Any]) -> float | None:
        value = run.get("heartbeat_at")
        if not value:
            return None
        try:
            heartbeat = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        return max(0.0, (datetime.now(UTC) - heartbeat).total_seconds())

    def log_digest(self, run_id: str, *, max_tail_lines: int = 40) -> dict[str, Any]:
        run = self.get(run_id)
        log_path = Path(run["log_path"])
        stderr_log_path = Path(run.get("stderr_log_path") or (log_path.parent / "stderr.log"))
        raw = log_path.read_bytes() if log_path.exists() else b""
        stderr_raw = stderr_log_path.read_bytes() if stderr_log_path.exists() else b""
        text = raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        combined_text = text + "\n" + stderr_text
        lines = text.splitlines()
        stderr_lines = stderr_text.splitlines()
        tail_limit = max(0, min(int(max_tail_lines), 200))
        tail = [redact_text(line) for line in (lines[-tail_limit:] if tail_limit else [])]
        stderr_tail = [redact_text(line) for line in (stderr_lines[-tail_limit:] if tail_limit else [])]
        lower = combined_text.lower()
        if "out of memory" in lower or "cuda oom" in lower:
            error_class = "oom"
            next_action = "Reduce batch size, inspect memory pressure, then rerun or mark failed_resource."
        elif "traceback" in lower or "exception" in lower:
            error_class = "exception"
            next_action = "Inspect the bounded tail and fix the first exception before rerunning."
        elif "error" in lower or "failed" in lower:
            error_class = "error"
            next_action = "Inspect the bounded tail and decide retry, fix, or failure classification."
        else:
            error_class = "none"
            next_action = "No obvious error pattern in bounded log tail."
        return {
            "ok": True,
            "run_id": run_id,
            "status": run.get("status"),
            "log_path": str(log_path),
            "stderr_log_path": str(stderr_log_path),
            "bytes": len(raw),
            "stderr_bytes": len(stderr_raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr_raw).hexdigest(),
            "line_count": len(lines),
            "stderr_line_count": len(stderr_lines),
            "heartbeat_age_seconds": self._heartbeat_age_seconds(run),
            "last_semantic_events": tail,
            "last_stderr_digest": stderr_tail,
            "top_error_class": error_class,
            "suggested_next_action": next_action,
        }
