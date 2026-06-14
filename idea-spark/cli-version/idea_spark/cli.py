from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import config_path, load_config, set_tools_enabled
from .tools import HANDLERS


def _print_json(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("success", True) else 1


def _load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "stdin", False):
        text = sys.stdin.read()
        return json.loads(text) if text.strip() else {}
    json_file = getattr(args, "json_file", None)
    if json_file:
        return json.loads(Path(json_file).read_text(encoding="utf-8"))
    return {}


def _dispatch_operation(operation: str, payload: dict[str, Any]) -> int:
    handler = HANDLERS.get(operation)
    if handler is None:
        return _print_json({"success": False, "error": "unknown operation", "operation": operation})
    try:
        result = json.loads(handler(payload))
    except Exception as exc:
        return _print_json({"success": False, "error": str(exc), "operation": operation})
    if not isinstance(result, dict):
        return _print_json({"success": False, "error": "handler returned non-object JSON", "operation": operation})
    return _print_json(result)


def setup_parser(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("config", help="Show or update Idea-Spark plugin config.")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="Print the active Idea-Spark plugin config as JSON.")
    set_tools = config_sub.add_parser("set-tools", help="Explicitly enable or disable Hermes tool registration.")
    set_tools.add_argument("enabled", choices=["true", "false"], help="Whether to register idea_spark_* tools on plugin load.")

    call = sub.add_parser("call", help="Dispatch an Idea-Spark ledger operation by canonical tool name.")
    call.add_argument("operation", help="Canonical operation name, e.g. idea_spark_room_create.")
    payload = call.add_mutually_exclusive_group()
    payload.add_argument("--json-file", help="Path to a JSON object payload file.")
    payload.add_argument("--stdin", action="store_true", help="Read a JSON object payload from stdin.")


def main_from_args(args: argparse.Namespace) -> int:
    if args.command == "config" and args.config_command == "show":
        return _print_json({"success": True, "path": str(config_path()), "config": load_config()})
    if args.command == "config" and args.config_command == "set-tools":
        enabled = args.enabled == "true"
        path = set_tools_enabled(enabled)
        return _print_json({"success": True, "path": str(path), "tools_enabled": enabled})
    if args.command == "call":
        try:
            payload = _load_payload(args)
        except Exception as exc:
            return _print_json({"success": False, "error": f"invalid JSON payload: {exc}", "operation": args.operation})
        if not isinstance(payload, dict):
            return _print_json({"success": False, "error": "payload must be a JSON object", "operation": args.operation})
        return _dispatch_operation(args.operation, payload)
    return _print_json({"success": False, "error": "unknown command"})


def hermes_main_from_args(args: argparse.Namespace) -> None:
    raise SystemExit(main_from_args(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Idea-Spark shared-ledger CLI")
    setup_parser(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    return main_from_args(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
