from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..shared import which
from .builtins import register_builtin_runtime_tools
from .models import RuntimeBinaryMatch, RuntimeTool, RuntimeToolStatus
from .registry import get_runtime_tool_factory, list_runtime_tool_names


class RuntimeToolService:
    def __init__(self, home: Path) -> None:
        self.home = home
        register_builtin_runtime_tools(home=home)

    def get_tool(self, name: str) -> RuntimeTool:
        return get_runtime_tool_factory(name)(home=self.home)

    def list_tool_names(self) -> list[str]:
        return list_runtime_tool_names()

    def status(self, name: str) -> RuntimeToolStatus:
        return self.get_tool(name).status()

    def install(self, name: str) -> RuntimeToolStatus:
        return self.get_tool(name).install()

    def all_statuses(self) -> dict[str, RuntimeToolStatus]:
        return {name: self.status(name) for name in self.list_tool_names()}

    def resolve_binary(
        self,
        binary: str,
        *,
        preferred_tools: Iterable[str] | None = None,
        allow_system_fallback: bool = True,
    ) -> RuntimeBinaryMatch:
        normalized = str(binary or "").strip()
        if not normalized:
            return {"binary": None, "path": None, "source": None, "root": None, "bin_dir": None}

        names = list(preferred_tools or self.list_tool_names())
        for name in names:
            match = self.get_tool(name).resolve_binary(normalized)
            if isinstance(match, dict) and match.get("path"):
                return match

        system_path = which(normalized) if allow_system_fallback else None
        return {
            "binary": normalized,
            "path": system_path,
            "source": "path" if system_path else None,
            "root": None,
            "bin_dir": None,
        }


__all__ = ["RuntimeToolService"]
