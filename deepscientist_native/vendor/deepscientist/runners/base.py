from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunRequest:
    quest_id: str
    quest_root: Path
    worktree_root: Path | None
    run_id: str
    skill_id: str
    message: str
    model: str
    approval_policy: str
    sandbox_mode: str
    turn_reason: str = "user_message"
    turn_intent: str = "continue_stage"
    turn_mode: str = "stage_execution"
    reasoning_effort: str | None = None
    turn_id: str | None = None
    attempt_index: int = 1
    max_attempts: int = 1
    retry_context: dict[str, Any] | None = None


@dataclass(frozen=True)
class RunResult:
    ok: bool
    run_id: str
    model: str
    output_text: str
    exit_code: int
    history_root: Path
    run_root: Path
    stderr_text: str
