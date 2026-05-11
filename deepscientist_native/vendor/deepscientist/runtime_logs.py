from __future__ import annotations

from pathlib import Path
from typing import Any

from .shared import append_jsonl, ensure_dir, utc_now


LOG_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40}


class JsonlLogger:
    def __init__(self, root: Path, level: str = "info") -> None:
        self.root = ensure_dir(root)
        self.level = level if level in LOG_LEVELS else "info"
        self.path = self.root / "runtime.jsonl"

    def should_log(self, level: str) -> bool:
        return LOG_LEVELS.get(level, 20) >= LOG_LEVELS.get(self.level, 20)

    def log(self, level: str, event: str, **payload: Any) -> None:
        if not self.should_log(level):
            return
        append_jsonl(
            self.path,
            {
                "timestamp": utc_now(),
                "level": level,
                "event": event,
                "payload": payload,
            },
        )
