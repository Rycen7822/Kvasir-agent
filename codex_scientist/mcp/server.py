"""Minimal JSON-RPC stdio MCP server helpers for CodexScientist."""
from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload
from codexscientist_native.redaction import redact_text


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


def list_tools_payload() -> dict[str, Any]:
    return tools_list_payload()


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
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    if method == "initialize":
        return _jsonrpc_result(message_id, initialize_payload())
    if method == "tools/list":
        return _jsonrpc_result(message_id, list_tools_payload())
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if not isinstance(name, str) or not name:
            return _jsonrpc_error(message_id, -32602, "tools/call requires params.name")
        return _jsonrpc_result(message_id, _mcp_tool_result(call_tool_payload(name, arguments)))
    return _jsonrpc_error(message_id, -32601, f"Unsupported method: {method}")


def run_stdio(input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
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
