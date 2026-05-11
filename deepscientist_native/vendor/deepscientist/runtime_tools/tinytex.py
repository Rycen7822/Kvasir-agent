from __future__ import annotations

from pathlib import Path
from typing import Any

from ..tinytex import inspect_latex_runtime, install_tinytex, resolve_tinytex_binary


class TinyTeXRuntimeTool:
    tool_name = "tinytex"

    def __init__(self, home: Path) -> None:
        self.home = home

    def status(self) -> dict[str, Any]:
        return inspect_latex_runtime(self.home)

    def install(self) -> dict[str, Any]:
        return install_tinytex(self.home)

    def resolve_binary(self, binary: str) -> dict[str, Any]:
        return resolve_tinytex_binary(binary, self.home)


__all__ = ["TinyTeXRuntimeTool"]
