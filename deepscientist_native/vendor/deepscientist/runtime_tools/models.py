from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class RuntimeTool(Protocol):
    tool_name: str

    def status(self) -> dict[str, Any]:
        ...

    def install(self) -> dict[str, Any]:
        ...

    def resolve_binary(self, binary: str) -> dict[str, Any]:
        ...


RuntimeToolFactory = Callable[..., RuntimeTool]
RuntimeBinaryMatch = dict[str, Any]
RuntimeToolStatus = dict[str, Any]

__all__ = [
    "RuntimeBinaryMatch",
    "RuntimeTool",
    "RuntimeToolFactory",
    "RuntimeToolStatus",
]
