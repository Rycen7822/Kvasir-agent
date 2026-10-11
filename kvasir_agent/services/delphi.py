"""Project-bound Delphi calls; each component executes in an isolated process."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

_FIELDS = {
    "idea_spark": {
        "open": ({"goal", "request_id"}, {"mode", "input_path"}),
        "status": ({"room_id"}, {"limit"}),
        "prepare": ({"room_id", "agent_id", "input_path", "request_id"}, {"role"}),
        "collect": ({"room_id", "receipt_paths"}, set()),
        "update": ({"room_id", "input_path"}, set()),
        "finish": ({"room_id", "input_path"}, set()),
    },
    "ponder_forge": {
        "open": ({"goal", "request_id"}, {"effort", "input_path"}),
        "status": ({"run_id"}, {"task_id", "limit"}),
        "plan": ({"run_id", "input_path"}, set()),
        "prepare": ({"run_id", "input_path", "request_id"}, set()),
        "record": ({"run_id", "task_id", "status"}, {"host_agent_id"}),
        "collect": ({"run_id"}, {"task_id", "file_path", "receipt_paths", "input_path", "status"}),
        "verify": ({"run_id", "input_path", "request_id"}, set()),
        "finish": ({"run_id", "file_path"}, {"status", "input_path"}),
    },
}


def call_delphi(args: dict) -> dict:
    workflow, action = args["workflow"], args["action"]
    if action not in _FIELDS[workflow]:
        return {"ok": False, "error_type": "invalid_arguments",
                "error": f"{workflow} supports: {', '.join(_FIELDS[workflow])}."}
    required, optional = _FIELDS[workflow][action]
    missing = required - args.keys()
    extra = args.keys() - required - optional - {"project", "workflow", "action"}
    if missing or extra:
        return {"ok": False, "error_type": "invalid_arguments",
                "error": f"Required: {', '.join(sorted(required))}. Unused: {', '.join(sorted(extra))}."}
    if action == "collect" and workflow == "ponder_forge":
        batch = "receipt_paths" in args
        if (batch and set(args) & {"task_id", "file_path", "input_path", "status"}) or (
            not batch and not {"task_id", "file_path"}.issubset(args)
        ):
            return {"ok": False, "error_type": "invalid_arguments",
                    "error": "Collect requires receipt_paths, or task_id + file_path with optional metadata input_path/status."}
    project = Path(args["project"]).expanduser()
    if not project.is_absolute() or not project.is_dir():
        return {"ok": False, "error_type": "invalid_arguments", "error": "project must be an existing absolute directory."}
    project = project.resolve()
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DELPHI_HOME": str(project / ".kvasir" / "delphi"),
           "PYTHONPATH": str(root) + os.pathsep + os.environ.get("PYTHONPATH", ""),
           "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run([sys.executable, "-m", "delphi.mcp"],
                              input=json.dumps({**args, "project": str(project)}),
                              cwd=project, env=env, capture_output=True, text=True, timeout=60)
        if proc.returncode:
            return {"ok": False, "error_type": "state_error", "error": "Delphi worker bridge failed; inspect project state before retrying."}
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error_type": "timeout", "error": "State operation timed out. Query status and reuse the same allocation request_id."}
