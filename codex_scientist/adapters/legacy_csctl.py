from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from .cli import normalize_envelope

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PLUGIN_ROOT / "scripts"
for path in (PLUGIN_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import cs_native_cli  # type: ignore  # noqa: E402


def run(argv: list[str] | None = None) -> dict[str, Any]:
    """Run legacy csctl parser logic and return a normalized envelope.

    This adapter is intentionally thin: it exists so `scripts/csctl.py` can stay
    compatible while new service-layer code grows behind `scripts/csctl.py`.
    """

    parser = cs_native_cli.build_parser()
    args = parser.parse_args(argv)
    if args.project_root:
        project_root = Path(args.project_root).expanduser().resolve()
        os.environ["CODEXSCIENTIST_PROJECT_ROOT"] = str(project_root)
        os.chdir(project_root)
    if not hasattr(args, "func"):
        return normalize_envelope({"ok": False, "error": "No command provided", "error_type": "usage", "recoverable": True})
    return normalize_envelope(args.func(args))
