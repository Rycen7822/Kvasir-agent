from __future__ import annotations

from .codex import CodexRunner
from .registry import register_runner


def register_builtin_runners(*, codex_runner: CodexRunner) -> None:
    register_runner("codex", lambda **_: codex_runner)
