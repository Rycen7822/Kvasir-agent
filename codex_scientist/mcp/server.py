"""Minimal JSON-RPC stdio MCP server helpers for CodexScientist."""
from __future__ import annotations

import json
import sys
from typing import Any, TextIO, cast

from codex_scientist.mcp.tool_registry import (
    call_tool,
    is_tool_registered_for_mcp,
    mcp_tool_not_registered_payload,
    tools_list_payload,
)
from codex_scientist.runtime.redaction import redact_text


def initialize_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "server": "codexscientist_mcp",
        "protocol": "mcp",
        "protocolVersion": "2024-11-05",
        "transport": "stdio",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "codexscientist_mcp", "version": "0.1.0"},
    }


def list_tools_payload(args: dict[str, Any] | None = None) -> dict[str, Any]:
    return tools_list_payload(args)


def call_tool_payload(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    return call_tool(name, args or {})


def _jsonrpc_result(message_id: object, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _mcp_tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["structuredContent"] = payload
    result["isError"] = not bool(payload.get("ok", False))
    result["content"] = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
    return result


def _jsonrpc_error(message_id: object, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": redact_text(message)}}


def handle_jsonrpc_message(message: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one newline-delimited JSON-RPC request.

    This intentionally implements only the local stdio methods CodexScientist
    needs for deterministic MCP registration smoke tests. Notifications without
    an id are accepted and ignored.
    """
    message_id = message.get("id")
    if message_id is None:
        return None
    method = message.get("method")
    raw_params = message.get("params")
    params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
    if method == "initialize":
        return _jsonrpc_result(message_id, initialize_payload())
    if method == "tools/list":
        return _jsonrpc_result(message_id, list_tools_payload(params))
    if method == "tools/call":
        name = params.get("name")
        raw_arguments = params.get("arguments")
        arguments: dict[str, Any] = raw_arguments if isinstance(raw_arguments, dict) else {}
        if not isinstance(name, str) or not name:
            return _jsonrpc_error(message_id, -32602, "tools/call requires params.name")
        if not is_tool_registered_for_mcp(name, arguments):
            return _jsonrpc_result(message_id, _mcp_tool_result(mcp_tool_not_registered_payload(name)))
        if name == "cs_tool_schema":
            schema_name = arguments.get("name")
            if isinstance(schema_name, str) and schema_name and not is_tool_registered_for_mcp(schema_name, arguments):
                return _jsonrpc_result(message_id, _mcp_tool_result(mcp_tool_not_registered_payload(schema_name)))
        return _jsonrpc_result(message_id, _mcp_tool_result(call_tool_payload(name, arguments)))
    return _jsonrpc_error(message_id, -32601, f"Unsupported method: {method}")


def run_stdio(input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> int:
    if input_stream is None:
        input_stream = cast(TextIO, sys.stdin)
    if output_stream is None:
        output_stream = cast(TextIO, sys.stdout)
    for raw_line in input_stream:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                response = _jsonrpc_error(None, -32600, "JSON-RPC message must be an object")
            else:
                response = handle_jsonrpc_message(message)
        except json.JSONDecodeError as exc:
            response = _jsonrpc_error(None, -32700, f"Invalid JSON: {exc.msg}")
        if response is not None:
            output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
            output_stream.flush()
    return 0
