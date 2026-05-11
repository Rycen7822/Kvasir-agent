#!/usr/bin/env python3
"""Codex-native DeepScientist control script.

This is the primary native integration surface for Codex CLI. It imports the
vendored DeepScientist runtime directly and invokes curated ds_* handlers. It is
not an MCP server and it never calls the external npm `ds` command for normal
operation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


def _load_native():
    from deepscientist_native import schemas, tools
    return schemas, tools


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _parse_scalar(value: str) -> Any:
    text = value.strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if text.lower() in {"null", "none"}:
        return None
    if text.startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    try:
        if re_match_int(text):
            return int(text)
        if re_match_float(text):
            return float(text)
    except Exception:
        return value
    return value


def re_match_int(text: str) -> bool:
    return bool(text) and text.lstrip("+-").isdigit()


def re_match_float(text: str) -> bool:
    if not text or text.count(".") != 1:
        return False
    left, right = text.lstrip("+-").split(".", 1)
    return (left.isdigit() or left == "") and right.isdigit()


def _load_args(json_text: str | None, arg_items: list[str] | None, stdin_json: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if stdin_json:
        raw = sys.stdin.read()
        if raw.strip():
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                raise SystemExit("stdin JSON must be an object")
            payload.update(loaded)
    if json_text:
        loaded = json.loads(json_text)
        if not isinstance(loaded, dict):
            raise SystemExit("--json must be a JSON object")
        payload.update(loaded)
    for item in arg_items or []:
        if "=" not in item:
            raise SystemExit(f"--arg expects key=value, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit("--arg key must not be empty")
        payload[key] = _parse_scalar(value)
    return payload


def _tool_map() -> dict[str, Any]:
    schemas, tools = _load_native()
    mapping: dict[str, Any] = {}
    for schema in schemas.ALL_SCHEMAS:
        name = schema["name"]
        handler = getattr(tools, name, None)
        if handler is not None:
            mapping[name] = handler
    return mapping


def _schemas_by_name(*, include_legacy: bool = False) -> dict[str, dict[str, Any]]:
    schemas, _tools = _load_native()
    schema_list = schemas.ALL_SCHEMAS if include_legacy else schemas.PUBLIC_SCHEMAS
    return {schema["name"]: schema for schema in schema_list}


def _legacy_alias_to_canonical() -> dict[str, str]:
    schemas, _tools = _load_native()
    return dict(getattr(schemas, "LEGACY_ALIAS_TO_CANONICAL", {}))


def _parse_tool_response(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        payload = raw
    else:
        payload = json.loads(str(raw))
    if not isinstance(payload, dict):
        payload = {"ok": True, "result": payload}
    payload.setdefault("ok", True)
    return payload


def _friendly_payload(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload.setdefault("transport", "codex-native-cli")
    payload.setdefault("mcp", False)
    legacy_aliases = _legacy_alias_to_canonical()
    if tool_name in legacy_aliases:
        payload.setdefault("deprecated_alias", True)
        payload.setdefault("legacy_tool", tool_name)
        payload.setdefault("canonical_tool", legacy_aliases[tool_name])
    if tool_name == "ds_new_quest" and "quest_id" not in payload:
        quest = payload.get("quest") if isinstance(payload.get("quest"), dict) else {}
        if quest.get("quest_id"):
            payload["quest_id"] = quest.get("quest_id")
    if tool_name == "ds_memory_write":
        card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
        alias = payload.get("memory_kind_alias") if isinstance(payload.get("memory_kind_alias"), dict) else {}
        payload.setdefault("kind", card.get("kind") or alias.get("normalized"))
        tags = list(card.get("tags") or [])
        semantic_tag = alias.get("semantic_tag")
        if semantic_tag and semantic_tag not in tags:
            tags.append(semantic_tag)
        payload.setdefault("tags", tags)
    if tool_name == "ds_artifact_record":
        artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
        if artifact.get("path") and "path" not in payload:
            payload["path"] = artifact.get("path")
    return payload


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    mapping = _tool_map()
    if name not in mapping:
        return {"ok": False, "error": f"Unknown tool: {name}", "available_tools": sorted(mapping), "transport": "codex-native-cli", "mcp": False}
    raw = mapping[name](args)
    payload = _parse_tool_response(raw)
    return _friendly_payload(name, payload)


def emit(payload: dict[str, Any], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))


def command_list_tools(args: argparse.Namespace) -> dict[str, Any]:
    schemas = _schemas_by_name(include_legacy=False)
    tools = [
        {
            "name": name,
            "description": schema.get("description", ""),
            "required": (schema.get("input_schema") or {}).get("required", []),
        }
        for name, schema in sorted(schemas.items())
    ]
    return {"ok": True, "transport": "codex-native-cli", "mcp": False, "count": len(tools), "tools": tools}


def command_schema(args: argparse.Namespace) -> dict[str, Any]:
    schemas = _schemas_by_name(include_legacy=bool(args.tool_name))
    if args.tool_name:
        schema = schemas.get(args.tool_name)
        if schema is None:
            public_schemas = _schemas_by_name(include_legacy=False)
            return {"ok": False, "error": f"Unknown tool schema: {args.tool_name}", "available_tools": sorted(public_schemas), "transport": "codex-native-cli", "mcp": False}
        payload = {"ok": True, "transport": "codex-native-cli", "mcp": False, "schema": schema}
        legacy_aliases = _legacy_alias_to_canonical()
        if args.tool_name in legacy_aliases:
            payload.update({"deprecated_alias": True, "legacy_tool": args.tool_name, "canonical_tool": legacy_aliases[args.tool_name]})
        return payload
    return {"ok": True, "transport": "codex-native-cli", "mcp": False, "schemas": list(schemas.values())}


def command_call(args: argparse.Namespace) -> dict[str, Any]:
    payload = _load_args(args.json, args.arg, args.stdin_json)
    return call_tool(args.tool_name, payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeepScientist Codex-native dsctl. No MCP, no external ds.")
    parser.add_argument("--project-root", help="Project root whose ./DeepScientist runtime should be used. Defaults to cwd or DEEPSCIENTIST_PROJECT_ROOT.")
    parser.add_argument("--format", choices=["json", "pretty"], default="pretty")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("list-tools", help="List native ds_* tools exposed to Codex")
    p.add_argument("--format", choices=["json", "pretty"], default=None)
    p.set_defaults(func=command_list_tools)

    p = sub.add_parser("schema", help="Print one tool schema or all schemas")
    p.add_argument("tool_name", nargs="?")
    p.add_argument("--format", choices=["json", "pretty"], default=None)
    p.set_defaults(func=command_schema)

    p = sub.add_parser("doctor", help="Run native runtime diagnostics")
    p.add_argument("--format", choices=["json", "pretty"], default=None)
    p.set_defaults(func=lambda ns: call_tool("ds_doctor", {}))

    p = sub.add_parser("call", help="Call a native ds_* tool")
    p.add_argument("tool_name")
    p.add_argument("--json", help="JSON object with tool arguments")
    p.add_argument("--arg", action="append", default=[], help="Additional key=value argument; may be repeated")
    p.add_argument("--stdin-json", action="store_true", help="Read a JSON object from stdin")
    p.add_argument("--format", choices=["json", "pretty"], default=None)
    p.set_defaults(func=command_call)

    # Common convenience shortcuts.
    for tool_name in ["ds_doctor", "ds_list_quests", "ds_get_quest_state", "ds_events", "ds_new_quest", "ds_set_active_quest", "ds_memory_search", "ds_memory_write", "ds_artifact_record", "ds_bash_exec"]:
        p = sub.add_parser(tool_name, help=f"Shortcut for call {tool_name}")
        p.add_argument("--json", help="JSON object with tool arguments")
        p.add_argument("--arg", action="append", default=[], help="Additional key=value argument; may be repeated")
        p.add_argument("--stdin-json", action="store_true", help="Read a JSON object from stdin")
        p.add_argument("--format", choices=["json", "pretty"], default=None)
        p.set_defaults(func=lambda ns, tn=tool_name: call_tool(tn, _load_args(ns.json, ns.arg, ns.stdin_json)))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.project_root:
        project_root = Path(args.project_root).expanduser().resolve()
        os.environ["DEEPSCIENTIST_PROJECT_ROOT"] = str(project_root)
        os.chdir(project_root)
    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2
    fmt = getattr(args, "format", None) or "pretty"
    payload = args.func(args)
    emit(payload, fmt)
    return 0 if payload.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
