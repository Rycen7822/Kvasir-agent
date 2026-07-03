from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

try:
    from .tools import ponder_forge_start
except ImportError:
    spec = importlib.util.spec_from_file_location("ponder_forge_local_tools", Path(__file__).resolve().parent / "tools.py")
    if spec is None or spec.loader is None:
        raise
    _tools = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_tools)
    ponder_forge_start = _tools.ponder_forge_start


def start_ponder_forge_command(ctx: Any, raw_args: str) -> str:
    goal = (raw_args or "").strip()
    if not goal:
        return json.dumps({"success": False, "error": "missing complex problem"}, ensure_ascii=False)
    result = json.loads(ponder_forge_start({"goal": goal, "profile": "auto"}))
    if result.get("success"):
        result["instruction"] = f"Call ponder_forge_plan with run_id={result['run_id']}. Do not answer finally before ponder_forge_finalize."
    return json.dumps(result, ensure_ascii=False)
