"""Small file/state bridge for native hosts, never a model or agent runner."""
from __future__ import annotations

import fcntl
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid


def read_input(args: dict) -> dict:
    if not args.get("input_path"):
        return {}
    value = json.loads(Path(args["input_path"]).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input_path must contain a JSON object")
    return value


def check_fields(data: dict, allowed: set, required: set = frozenset()) -> None:
    if data.keys() - allowed or required - data.keys():
        raise ValueError(f"Input fields: {', '.join(sorted(allowed))}; required: {', '.join(sorted(required))}")


def text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def templates(directory: Path, examples: dict) -> dict:
    paths = {}
    for action, value in examples.items():
        path = directory / "inputs" / f"{action}.json"
        if not path.exists():
            write_json(path, value)
        paths[action] = str(path)
    return paths


def next_call(args: dict, action: str, **fields) -> dict:
    identity = {key: args[key] for key in ("room_id", "run_id") if key in args}
    return {"name": "ka_delphi", "arguments": {
        "project": args["project"], "workflow": args["workflow"], "action": action,
        **identity, **fields}}


def worker_delivery(instructions: str, output: Path, scratch: Path) -> str:
    scratch.mkdir(parents=True, exist_ok=True)
    return (instructions + f"\n\n# Complete-file delivery\n"
            f"Write the complete research report to {output}. Keep temporary notes in {scratch}. "
            "Read supplied input files in full when needed. Return the absolute output path and a brief summary. "
            "If writing fails, return the complete body. The parent collects and updates state; "
            "use native host tools for research, not Delphi ledger tools. Do not launch more agents.")


def allocated(args: dict, payload: dict, execute) -> dict:
    """Commit reservation before effects; interrupted calls recover the same identities."""
    directory = Path(os.environ["DELPHI_HOME"]) / "mcp"
    directory.mkdir(parents=True, exist_ok=True)
    scope = args.get("room_id", args.get("run_id", ""))
    key = (args["workflow"], args["action"], scope, args["request_id"])
    signature = json.dumps({"arguments": args, "input": payload}, sort_keys=True, ensure_ascii=False)
    with (directory / "allocations.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with sqlite3.connect(directory / "allocations.sqlite3") as conn:
            conn.execute("""create table if not exists allocations (
                workflow text, action text, scope text, request_id text, input_json text,
                identities_json text, result_json text,
                primary key(workflow, action, scope, request_id))""")
            row = conn.execute("select input_json, identities_json, result_json from allocations "
                               "where workflow=? and action=? and scope=? and request_id=?", key).fetchone()
            if row:
                if row[0] != signature:
                    raise ValueError("request_id already belongs to a different allocation input; use a new request_id")
                identities = json.loads(row[1])
                if row[2]:
                    return {**json.loads(row[2]), "idempotent": True,
                            "retry_note": "Same allocation. Confirm native agent state before dispatching again."}
            else:
                count = len(payload.get("tasks", [])) if args["action"] == "prepare" and args["workflow"] == "ponder_forge" else 1
                identities = {"room_id": "room_" + uuid.uuid4().hex,
                              "run_id": "run_" + uuid.uuid4().hex,
                              "artifact_id": "artifact_" + uuid.uuid4().hex,
                              "task_ids": ["task_" + uuid.uuid4().hex for _ in range(count)]}
                conn.execute("insert into allocations values(?,?,?,?,?,?,NULL)",
                             (*key, signature, json.dumps(identities)))
                conn.commit()
            result = execute(identities)
            conn.execute("update allocations set result_json=? "
                         "where workflow=? and action=? and scope=? and request_id=?",
                         (json.dumps(result, ensure_ascii=False), *key))
            conn.commit()
            return result


def main() -> None:
    try:
        args = json.load(sys.stdin)
        payload = read_input(args)
        component = {"idea_spark": "idea-spark", "ponder_forge": "ponder-forge"}[args["workflow"]]
        adapter = importlib.import_module(f"delphi.{component}.mcp")
        adapter.validate(args, payload)
        if args["action"] in {"open", "prepare", "verify"}:
            result = allocated(args, payload, lambda ids: adapter.dispatch(args, payload, ids))
        else:
            result = adapter.dispatch(args, payload, {})
        print(json.dumps({"ok": True, "workflow": args["workflow"], **result}, ensure_ascii=False))
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"ok": False, "error_type": "invalid_input", "error": str(exc)[:400]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
