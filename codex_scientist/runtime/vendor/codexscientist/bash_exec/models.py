from __future__ import annotations

from dataclasses import dataclass
import threading
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AttachToken:
    token: str
    quest_root: Path
    bash_id: str
    expires_at: float


@dataclass(slots=True)
class TerminalClient:
    client_id: str
    send_text: Any
    send_binary: Any
    close: Any
    send_lock: threading.Lock
