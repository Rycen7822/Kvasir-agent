from __future__ import annotations

from pathlib import Path

from .registry import register_runtime_tool
from .tinytex import TinyTeXRuntimeTool


def register_builtin_runtime_tools(*, home=None) -> None:
    def _tinytex_factory(**kwargs):
        selected_home = kwargs.get("home") or home
        if selected_home is None:
            raise ValueError("Runtime tool factories require `home`.")
        return TinyTeXRuntimeTool(Path(selected_home))

    register_runtime_tool("tinytex", _tinytex_factory)


__all__ = ["register_builtin_runtime_tools"]
