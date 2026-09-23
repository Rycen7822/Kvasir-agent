from __future__ import annotations

from .base import RunRequest, RunResult
from .registry import get_runner_factory, list_runner_names, register_runner

__all__ = [
    "CodexRunner",
    "RunRequest",
    "RunResult",
    "get_runner_factory",
    "list_runner_names",
    "register_builtin_runners",
    "register_runner",
]


def __getattr__(name: str):
    if name == "CodexRunner":
        from .codex import CodexRunner

        return CodexRunner
    if name == "register_builtin_runners":
        from .builtins import register_builtin_runners

        return register_builtin_runners
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
