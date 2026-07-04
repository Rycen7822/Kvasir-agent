from __future__ import annotations

import json
import importlib.util
from pathlib import Path

try:
    from .cli import start_run
except ImportError:
    _cli_spec = importlib.util.spec_from_file_location("ponder_forge_local_cli", Path(__file__).resolve().parent / "cli.py")
    if _cli_spec is None or _cli_spec.loader is None:
        raise
    _cli = importlib.util.module_from_spec(_cli_spec)
    _cli_spec.loader.exec_module(_cli)
    start_run = _cli.start_run

INSTALLED_CLI = "${HERMES_HOME:-$HOME/.hermes}/plugins/ponder_forge/cli.py"


def start_ponder_forge_command(ctx, raw_args: str) -> str:
    del ctx
    goal = (raw_args or "").strip()
    if not goal:
        return json.dumps({"success": False, "error": "missing complex problem"}, ensure_ascii=False)
    result = {"success": True, **start_run(goal, profile="auto")}
    run_id = result["run_id"]
    result["instruction"] = (
        f"Use terminal: python3 {INSTALLED_CLI} plan --run-id {run_id}; "
        f"then python3 {INSTALLED_CLI} delegations --run-id {run_id}. "
        "Call native delegate_task with the lane coordinator role=\"orchestrator\" payloads; "
        "each lane returns one JSON report with child_reports, then submit-report through the CLI."
    )
    return json.dumps(result, ensure_ascii=False)
