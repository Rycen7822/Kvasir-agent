from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator, TextIO

if os.name == "nt":  # pragma: no cover - exercised on Windows
    import msvcrt
else:  # pragma: no cover - exercised on POSIX
    import fcntl


def _ensure_lockable_file(handle: TextIO) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() > 0:
        handle.seek(0)
        return
    handle.write("\0")
    handle.flush()
    handle.seek(0)


def _lock_handle(handle: TextIO) -> None:
    if os.name == "nt":  # pragma: no cover - exercised on Windows
        _ensure_lockable_file(handle)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_handle(handle: TextIO) -> None:
    if os.name == "nt":  # pragma: no cover - exercised on Windows
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def advisory_file_lock(path: Path) -> Iterator[TextIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        _lock_handle(handle)
        try:
            yield handle
        finally:
            _unlock_handle(handle)
