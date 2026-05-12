#!/usr/bin/env python3
"""CodexScientist MCP stdio entrypoint and smoke-test helper."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from codex_scientist.mcp.server import call_tool_payload, initialize_payload, list_tools_payload, run_stdio  # noqa: E402


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _run_smoke(argv: list[str]) -> int:
    if not argv or argv[0] == "initialize":
        _emit(initialize_payload())
        return 0
    if argv[0] == "tools/list":
        _emit(list_tools_payload())
        return 0
    if argv[0] == "call" and len(argv) >= 2:
        args = json.loads(argv[2]) if len(argv) >= 3 else {}
        if not isinstance(args, dict):
            raise SystemExit("call args must be a JSON object")
        _emit(call_tool_payload(argv[1], args))
        return 0
    raise SystemExit("--stdio-smoke expects initialize, tools/list, or call <tool> <json>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CodexScientist MCP server")
    parser.add_argument("--stdio-smoke", nargs=argparse.REMAINDER, help="Run deterministic stdio smoke helper")
    args = parser.parse_args(argv)
    if args.stdio_smoke is not None:
        return _run_smoke(args.stdio_smoke)
    return run_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
