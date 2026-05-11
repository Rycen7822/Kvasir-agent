from __future__ import annotations

import re

from .models import RuntimeToolFactory


_RUNTIME_TOOL_FACTORIES: dict[str, RuntimeToolFactory] = {}
_RUNTIME_TOOL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _normalize_runtime_tool_name(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if not normalized or not _RUNTIME_TOOL_NAME_PATTERN.fullmatch(normalized):
        raise ValueError("Runtime tool name must match `^[a-z0-9][a-z0-9_-]*$`.")
    return normalized


def register_runtime_tool(name: str, factory: RuntimeToolFactory) -> None:
    _RUNTIME_TOOL_FACTORIES[_normalize_runtime_tool_name(name)] = factory


def get_runtime_tool_factory(name: str) -> RuntimeToolFactory:
    normalized = _normalize_runtime_tool_name(name)
    try:
        return _RUNTIME_TOOL_FACTORIES[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_RUNTIME_TOOL_FACTORIES)) or "none"
        raise KeyError(f"Unknown runtime tool `{normalized}`. Available runtime tools: {available}.") from exc


def list_runtime_tool_names() -> list[str]:
    return sorted(_RUNTIME_TOOL_FACTORIES)


__all__ = [
    "get_runtime_tool_factory",
    "list_runtime_tool_names",
    "register_runtime_tool",
]
