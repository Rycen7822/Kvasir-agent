from __future__ import annotations

import base64
import codecs
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, BinaryIO

if os.name != "nt":  # pragma: no cover - exercised on POSIX
    import pty
    import termios
else:  # pragma: no cover - exercised on Windows
    pty = None
    termios = None

from ..process_control import process_session_popen_kwargs, terminate_subprocess
from ..shared import ensure_dir, generate_id, read_json, utc_now
from .models import AttachToken, TerminalClient

BASH_STATUS_MARKER_PREFIX = "__DS_BASH_STATUS__"
BASH_CARRIAGE_RETURN_PREFIX = "__DS_BASH_CR__"
BASH_PROGRESS_PREFIX = "__DS_PROGRESS__"
BASH_TERMINAL_PROMPT_PREFIX = "__DS_TERMINAL_PROMPT__"
TERMINAL_FINAL_STATUSES = {"completed", "failed", "terminated"}
TERMINAL_REPLAY_LIMIT_BYTES = 1_500_000
TERMINAL_RUNTIME_POLL_SECONDS = 0.02
TERMINAL_STOP_GRACE_SECONDS = 5.0


def _normalize_string(value: object) -> str:
    return str(value or "").strip()


def _coerce_session_status(value: object) -> str:
    normalized = _normalize_string(value).lower()
    if normalized in TERMINAL_FINAL_STATUSES | {"running", "terminating"}:
        return normalized
    return "failed"


def _parse_progress_marker(line: str) -> dict[str, Any] | None:
    if not line.startswith(BASH_PROGRESS_PREFIX):
        return None
    raw = line[len(BASH_PROGRESS_PREFIX) :].strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_reason(reason: str | None) -> str:
    if not reason:
        return "none"
    return reason.replace('"', '\\"').replace("\n", "\\n")


def _status_marker(meta: dict[str, Any], *, status: str, exit_code: int | None, reason: str | None) -> str:
    return (
        f"{BASH_STATUS_MARKER_PREFIX} status={status} bash_id={meta.get('bash_id')} ts={utc_now()} "
        f"user_id={meta.get('started_by_user_id') or 'agent'} session_id={meta.get('session_id') or 'none'} "
        f"agent_id={meta.get('agent_id') or 'none'} agent_instance_id={meta.get('agent_instance_id') or 'none'} "
        f"exit_code={exit_code if exit_code is not None else 'none'} reason=\"{_safe_reason(reason)}\""
    )


def _parse_terminal_prompt_marker(line: str) -> dict[str, str] | None:
    if not line.startswith(BASH_TERMINAL_PROMPT_PREFIX):
        return None
    raw = line[len(BASH_TERMINAL_PROMPT_PREFIX) :].strip()
    if not raw:
        return None
    payload: dict[str, str] = {}
    for token in raw.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        payload[key.strip()] = value
    return payload or None


def _atomic_write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f"{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _drain_buffer(
    buffer: str,
    append_line,
    *,
    flush_partial: bool = False,
    carriage_mode: str = "stream",
) -> str:
    while True:
        index_r = buffer.find("\r")
        index_n = buffer.find("\n")
        if index_r == -1 and index_n == -1:
            break
        if index_r != -1 and (index_n == -1 or index_r < index_n):
            segment = buffer[:index_r]
            if index_r + 1 < len(buffer) and buffer[index_r + 1] == "\n":
                buffer = buffer[index_r + 2 :]
                append_line(segment)
            else:
                buffer = buffer[index_r + 1 :]
                if carriage_mode == "stream":
                    append_line(segment, stream="carriage")
                else:
                    append_line(f"{BASH_CARRIAGE_RETURN_PREFIX}{segment}")
            continue
        segment = buffer[:index_n]
        buffer = buffer[index_n + 1 :]
        append_line(segment)
    if flush_partial and buffer:
        append_line(buffer, stream="partial")
        return ""
    return buffer


@dataclass(slots=True)
class _LaunchDescriptor:
    transport: str
    process: subprocess.Popen[bytes]
    process_group_id: int | None
    master_fd: int | None = None
    output_stream: BinaryIO | None = None


class TerminalRuntime:
    def __init__(
        self,
        *,
        quest_root: Path,
        bash_id: str,
        meta_path: Path,
        log_path: Path,
        terminal_log_path: Path,
        prompt_events_path: Path,
        env_payload: dict[str, str],
        command: str,
        launch_argv: list[str] | None,
        cwd: Path,
        transport_preference: str | None,
        on_finished,
    ) -> None:
        self.quest_root = quest_root
        self.bash_id = bash_id
        self.meta_path = meta_path
        self.log_path = log_path
        self.terminal_log_path = terminal_log_path
        self.prompt_events_path = prompt_events_path
        self.env_payload = dict(env_payload)
        self.command = command
        self.launch_argv = [str(item) for item in (launch_argv or []) if str(item).strip()]
        self.cwd = cwd
        self.transport_preference = _normalize_string(transport_preference).lower() or None
        self._on_finished = on_finished
        self._clients: dict[str, TerminalClient] = {}
        self._clients_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._replay_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._process_group_id: int | None = None
        self._master_fd: int | None = None
        self._output_stream: BinaryIO | None = None
        self._transport = "pipe"
        self._replay_chunks: deque[bytes] = deque()
        self._replay_bytes = 0
        self._prompt_offset = 0
        self._prompt_remainder = b""

    def start(self) -> dict[str, Any]:
        ensure_dir(self.meta_path.parent)
        ensure_dir(self.log_path.parent)
        self.terminal_log_path.touch()
        self.log_path.touch()
        self.prompt_events_path.touch()

        env_payload = os.environ.copy()
        env_payload.update(self.env_payload)
        env_payload.setdefault("PYTHONUNBUFFERED", "1")
        env_payload.setdefault("TERM", "xterm-256color")
        env_payload.setdefault("COLORTERM", "truecolor")
        launch = self._start_process(env_payload)

        with self._state_lock:
            self._transport = launch.transport
            self._master_fd = launch.master_fd
            self._output_stream = launch.output_stream
            self._process = launch.process
            self._process_group_id = launch.process_group_id

        meta = read_json(self.meta_path, {}) or {}
        meta["monitor_pid"] = None
        meta["process_pid"] = launch.process.pid
        meta["process_group_id"] = launch.process_group_id
        meta["transport"] = launch.transport
        meta["status"] = "running"
        meta["updated_at"] = utc_now()
        _atomic_write_json(self.meta_path, meta)
        self._append_log_entry(_status_marker(meta, status="running", exit_code=None, reason="none"), stream="system")
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"terminal-runtime-{self.bash_id}",
        )
        self._reader_thread.start()
        return meta

    def _start_process(self, env_payload: dict[str, str]) -> _LaunchDescriptor:
        argv = self.launch_argv or ["bash", "-lc", self.command]
        popen_kwargs = {
            "cwd": str(self.cwd),
            "env": env_payload,
            **process_session_popen_kwargs(hide_window=True),
        }
        allow_pty = (
            os.name != "nt"
            and pty is not None
            and termios is not None
            and self.transport_preference != "pipe"
        )
        if allow_pty:
            master_fd, slave_fd = pty.openpty()
            process = subprocess.Popen(
                argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                **popen_kwargs,
            )
            os.close(slave_fd)
            os.set_blocking(master_fd, False)
            return _LaunchDescriptor(
                transport="pty",
                process=process,
                process_group_id=os.getpgid(process.pid),
                master_fd=master_fd,
            )
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **popen_kwargs,
        )
        if process.stdout is None:
            raise RuntimeError("terminal_runtime_missing_stdout_pipe")
        return _LaunchDescriptor(
            transport="pipe",
            process=process,
            process_group_id=process.pid if os.name == "nt" else os.getpgid(process.pid),
            output_stream=process.stdout,
        )

    def is_alive(self) -> bool:
        process = self._process
        return process is not None and process.poll() is None

    def snapshot_replay(self) -> list[bytes]:
        with self._replay_lock:
            return list(self._replay_chunks)

    def attach_client(self, client: TerminalClient) -> None:
        with self._clients_lock:
            self._clients[client.client_id] = client

    def detach_client(self, client_id: str) -> None:
        with self._clients_lock:
            self._clients.pop(client_id, None)

    def write_input(self, data: str) -> None:
        if not data:
            return
        self.write_binary_input(data.encode("utf-8"))

    def write_binary_input(self, data: bytes) -> None:
        if not data:
            return
        process = self._process
        if process is None or process.poll() is not None:
            raise RuntimeError("terminal_runtime_inactive")
        with self._write_lock:
            if self._transport == "pty" and self._master_fd is not None:
                os.write(self._master_fd, data)
                return
            if process.stdin is None:
                raise RuntimeError("terminal_runtime_missing_stdin")
            process.stdin.write(data)
            process.stdin.flush()

    def resize(self, cols: int, rows: int) -> None:
        if self._transport != "pty" or self._master_fd is None or cols <= 0 or rows <= 0 or termios is None:
            return
        winsz = struct.pack("HHHH", rows, cols, 0, 0)
        with self._write_lock:
            termios.tcsetwinsize(self._master_fd, (rows, cols))
            try:
                import fcntl  # pragma: no cover - exercised on POSIX

                fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsz)
            except Exception:
                return

    def stop(self, *, reason: str = "runtime_shutdown", force: bool = False) -> None:
        self._stop_event.set()
        process = self._process
        if process is None:
            return
        terminate_subprocess(
            process,
            process_group_id=self._process_group_id,
            force=force,
            prefer_ctrl_break=True,
            grace_seconds=TERMINAL_STOP_GRACE_SECONDS,
        )

    def _append_replay(self, payload: bytes) -> None:
        if not payload:
            return
        with self._replay_lock:
            self._replay_chunks.append(payload)
            self._replay_bytes += len(payload)
            while self._replay_bytes > TERMINAL_REPLAY_LIMIT_BYTES and self._replay_chunks:
                removed = self._replay_chunks.popleft()
                self._replay_bytes -= len(removed)

    def _broadcast_output(self, payload: bytes) -> None:
        if not payload:
            return
        with self._clients_lock:
            clients = list(self._clients.values())
        stale: list[str] = []
        for client in clients:
            try:
                with client.send_lock:
                    client.send_binary(payload)
            except Exception:
                stale.append(client.client_id)
        if stale:
            with self._clients_lock:
                for client_id in stale:
                    self._clients.pop(client_id, None)

    def _broadcast_control(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        with self._clients_lock:
            clients = list(self._clients.values())
        stale: list[str] = []
        for client in clients:
            try:
                with client.send_lock:
                    client.send_text(encoded)
            except Exception:
                stale.append(client.client_id)
        if stale:
            with self._clients_lock:
                for client_id in stale:
                    self._clients.pop(client_id, None)

    def _append_terminal_display(self, text: str) -> None:
        if not text:
            return
        ensure_dir(self.terminal_log_path.parent)
        with self.terminal_log_path.open("ab") as handle:
            handle.write(text.encode("utf-8", errors="replace"))

    def _append_log_entry(self, line: str, *, stream: str = "stdout") -> None:
        meta = read_json(self.meta_path, {}) or {}
        seq = int(meta.get("latest_seq") or 0) + 1
        timestamp = utc_now()
        _append_jsonl(
            self.log_path,
            {
                "seq": seq,
                "stream": stream,
                "line": line,
                "timestamp": timestamp,
            },
        )
        progress = _parse_progress_marker(line)
        if progress is not None:
            progress.setdefault("ts", timestamp)
            _atomic_write_json(self.meta_path.parent / "progress.json", progress)
            meta["last_progress"] = progress
        if stream not in {"system", "prompt"}:
            meta["last_output_at"] = timestamp
            meta["last_output_seq"] = seq
        meta["latest_seq"] = seq
        meta["updated_at"] = timestamp
        _atomic_write_json(self.meta_path, meta)

    def _poll_prompt_events(self) -> None:
        if not self.prompt_events_path.exists():
            return
        with self.prompt_events_path.open("rb") as handle:
            handle.seek(self._prompt_offset)
            chunk = handle.read()
            self._prompt_offset = handle.tell()
        if not chunk:
            return
        payload = self._prompt_remainder + chunk
        parts = payload.split(b"\n")
        if payload and not payload.endswith(b"\n"):
            self._prompt_remainder = parts.pop()
        else:
            self._prompt_remainder = b""
        for raw_line in parts:
            line = raw_line.decode("utf-8", errors="replace").strip()
            marker = _parse_terminal_prompt_marker(line)
            if not marker:
                continue
            meta = read_json(self.meta_path, {}) or {}
            prompt_cwd_raw = str(marker.get("cwd_b64") or marker.get("cwd") or meta.get("cwd") or self.cwd)
            if marker.get("cwd_b64"):
                try:
                    prompt_cwd = base64.b64decode(prompt_cwd_raw.encode("ascii")).decode("utf-8")
                except Exception:
                    prompt_cwd = prompt_cwd_raw
            else:
                prompt_cwd = prompt_cwd_raw
            meta["cwd"] = prompt_cwd
            meta["last_prompt_at"] = str(marker.get("ts") or utc_now())
            meta["updated_at"] = utc_now()
            _atomic_write_json(self.meta_path, meta)

    def _consume_text(self, text: str, log_buffer: str) -> str:
        if not text:
            return log_buffer
        encoded = text.encode("utf-8", errors="replace")
        self._append_replay(encoded)
        self._append_terminal_display(text)
        self._broadcast_output(encoded)
        log_buffer += text
        return _drain_buffer(
            log_buffer,
            self._append_log_entry,
            flush_partial=True,
            carriage_mode="stream",
        )

    def _reader_loop(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        log_buffer = ""
        process = self._process
        try:
            if process is None:
                return
            if self._transport == "pty":
                log_buffer = self._reader_loop_pty(process, decoder, log_buffer)
            else:
                log_buffer = self._reader_loop_pipe(process, decoder, log_buffer)
            tail = decoder.decode(b"", final=True)
            log_buffer = self._consume_text(tail, log_buffer)
            if log_buffer:
                self._append_log_entry(log_buffer, stream="partial")
            exit_code = process.wait()
            meta = read_json(self.meta_path, {}) or {}
            stop_request = read_json(self.meta_path.parent / "stop_request.json", {}) or {}
            stop_reason = (
                _normalize_string(meta.get("stop_reason"))
                or _normalize_string(stop_request.get("reason"))
                or None
            )
            final_status = "terminated" if stop_reason else ("completed" if exit_code == 0 else "failed")
            self._append_log_entry(
                _status_marker(meta, status=final_status, exit_code=exit_code, reason=stop_reason),
                stream="system",
            )
            meta["status"] = final_status
            meta["exit_code"] = exit_code
            meta["finished_at"] = utc_now()
            meta["updated_at"] = utc_now()
            meta["stop_reason"] = stop_reason
            _atomic_write_json(self.meta_path, meta)
            self._broadcast_control(
                {
                    "type": "exit",
                    "bash_id": self.bash_id,
                    "status": final_status,
                    "exit_code": exit_code,
                    "stop_reason": stop_reason,
                    "finished_at": meta["finished_at"],
                }
            )
        finally:
            self._stop_event.set()
            if self._master_fd is not None:
                try:
                    os.close(self._master_fd)
                except OSError:
                    pass
                self._master_fd = None
            if self._output_stream is not None:
                try:
                    self._output_stream.close()
                except OSError:
                    pass
                self._output_stream = None
            if self._process is not None and self._process.stdin is not None:
                try:
                    self._process.stdin.close()
                except OSError:
                    pass
            self._on_finished(self.quest_root, self.bash_id)

    def _reader_loop_pty(
        self,
        process: subprocess.Popen[bytes],
        decoder,
        log_buffer: str,
    ) -> str:
        master_fd = self._master_fd
        if master_fd is None:
            return log_buffer
        while True:
            self._poll_prompt_events()
            if self._stop_event.is_set() and process.poll() is None:
                terminate_subprocess(
                    process,
                    process_group_id=self._process_group_id,
                    prefer_ctrl_break=True,
                    grace_seconds=TERMINAL_STOP_GRACE_SECONDS,
                )
            ready, _unused_w, _unused_x = select.select([master_fd], [], [], TERMINAL_RUNTIME_POLL_SECONDS)
            if ready:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    chunk = b""
                if chunk:
                    log_buffer = self._consume_text(decoder.decode(chunk), log_buffer)
            if process.poll() is not None:
                break
        while True:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError:
                chunk = b""
            if not chunk:
                break
            log_buffer = self._consume_text(decoder.decode(chunk), log_buffer)
        return log_buffer

    def _reader_loop_pipe(
        self,
        process: subprocess.Popen[bytes],
        decoder,
        log_buffer: str,
    ) -> str:
        output_stream = self._output_stream
        if output_stream is None:
            return log_buffer
        while True:
            if self._stop_event.is_set() and process.poll() is None:
                terminate_subprocess(
                    process,
                    process_group_id=self._process_group_id,
                    prefer_ctrl_break=True,
                    grace_seconds=TERMINAL_STOP_GRACE_SECONDS,
                )
            chunk = output_stream.read(4096)
            self._poll_prompt_events()
            if chunk:
                log_buffer = self._consume_text(decoder.decode(chunk), log_buffer)
                continue
            if process.poll() is not None:
                break
            time.sleep(TERMINAL_RUNTIME_POLL_SECONDS)
        return log_buffer


class TerminalRuntimeManager:
    def __init__(self, home: Path) -> None:
        self.home = home
        self._lock = threading.Lock()
        self._runtimes: dict[tuple[str, str], TerminalRuntime] = {}
        self._tokens: dict[str, AttachToken] = {}

    @staticmethod
    def _key(quest_root: Path, bash_id: str) -> tuple[str, str]:
        return (str(quest_root.resolve()), bash_id)

    def _handle_runtime_finished(self, quest_root: Path, bash_id: str) -> None:
        with self._lock:
            self._runtimes.pop(self._key(quest_root, bash_id), None)

    def get_runtime(self, quest_root: Path, bash_id: str) -> TerminalRuntime | None:
        with self._lock:
            runtime = self._runtimes.get(self._key(quest_root, bash_id))
        if runtime is not None and runtime.is_alive():
            return runtime
        return None

    def ensure_runtime(
        self,
        *,
        quest_root: Path,
        bash_id: str,
        meta_path: Path,
        log_path: Path,
        terminal_log_path: Path,
        prompt_events_path: Path,
        env_payload: dict[str, str],
        command: str,
        launch_argv: list[str] | None,
        cwd: Path,
        transport_preference: str | None = None,
    ) -> dict[str, Any]:
        runtime = self.get_runtime(quest_root, bash_id)
        if runtime is not None:
            return read_json(meta_path, {}) or {}
        created = TerminalRuntime(
            quest_root=quest_root,
            bash_id=bash_id,
            meta_path=meta_path,
            log_path=log_path,
            terminal_log_path=terminal_log_path,
            prompt_events_path=prompt_events_path,
            env_payload=env_payload,
            command=command,
            launch_argv=launch_argv,
            cwd=cwd,
            transport_preference=transport_preference,
            on_finished=self._handle_runtime_finished,
        )
        meta = created.start()
        with self._lock:
            self._runtimes[self._key(quest_root, bash_id)] = created
        return meta

    def issue_attach_token(self, quest_root: Path, bash_id: str, *, ttl_seconds: int = 60) -> AttachToken:
        self._cleanup_tokens()
        token = AttachToken(
            token=generate_id("tattach"),
            quest_root=quest_root.resolve(),
            bash_id=bash_id,
            expires_at=time.time() + max(5, ttl_seconds),
        )
        with self._lock:
            self._tokens[token.token] = token
        return token

    def resolve_attach_token(self, token_value: str) -> tuple[AttachToken | None, TerminalRuntime | None]:
        self._cleanup_tokens()
        with self._lock:
            token = self._tokens.get(token_value)
        if token is None or token.expires_at < time.time():
            return None, None
        runtime = self.get_runtime(token.quest_root, token.bash_id)
        return token, runtime

    def consume_attach_token(self, token_value: str) -> tuple[AttachToken | None, TerminalRuntime | None]:
        token, runtime = self.resolve_attach_token(token_value)
        if token is None:
            return None, None
        with self._lock:
            self._tokens.pop(token_value, None)
        return token, runtime

    def shutdown(self) -> None:
        with self._lock:
            runtimes = list(self._runtimes.values())
            self._runtimes.clear()
            self._tokens.clear()
        for runtime in runtimes:
            runtime.stop(reason="runtime_shutdown", force=False)

    def _cleanup_tokens(self) -> None:
        now = time.time()
        with self._lock:
            expired = [token for token, payload in self._tokens.items() if payload.expires_at < now]
            for token in expired:
                self._tokens.pop(token, None)
