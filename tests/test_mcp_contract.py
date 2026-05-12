from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def smoke(*args: str) -> dict:
    completed = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "cs_mcp.py"), "--stdio-smoke", *args],
        cwd=PLUGIN_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(completed.stdout)


def test_mcp_tool_registry_is_curated_cs_only():
    from codex_scientist.mcp.tool_registry import list_tool_specs

    tools = list_tool_specs()
    names = [tool.name for tool in tools]
    assert "cs_doctor" in names
    assert "cs_skill_search" in names
    assert "cs_skill_load" in names
    assert "cs_manifest_validate" in names
    assert "cs_queue_status" in names
    assert all(name.startswith("cs_") for name in names)
    assert not any(name.startswith("d" + "s_") or name.startswith("codexscientist_") for name in names)
    assert len(names) < 48


def test_mcp_stdio_smoke_initialize_list_and_call_doctor():
    init = smoke("initialize")
    assert init["ok"] is True
    assert init["server"] == "codexscientist_mcp"

    listed = smoke("tools/list")
    names = [tool["name"] for tool in listed["tools"]]
    assert "cs_doctor" in names
    assert "cs_skill_search" in names
    assert all(name.startswith("cs_") for name in names)

    doctor = smoke("call", "cs_doctor", "{}")
    assert doctor["ok"] is True
    assert doctor["transport"] == "codexscientist-mcp"
    assert doctor["tool"] == "cs_doctor"


def test_mcp_stdio_jsonrpc_initialize_list_and_call_status():
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "cs_status", "arguments": {}}},
    ]
    completed = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "cs_mcp.py")],
        cwd=PLUGIN_ROOT,
        input="\n".join(json.dumps(message) for message in messages) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]

    assert [response["id"] for response in responses] == [1, 2, 3]
    assert responses[0]["result"]["server"] == "codexscientist_mcp"
    assert responses[0]["result"]["protocolVersion"]
    assert responses[0]["result"]["serverInfo"]["name"] == "codexscientist_mcp"
    assert "tools" in responses[0]["result"]["capabilities"]
    tools = responses[1]["result"]["tools"]
    assert "cs_status" in [tool["name"] for tool in tools]
    assert all("inputSchema" in tool for tool in tools)
    assert responses[2]["result"]["ok"] is True
    assert responses[2]["result"]["tool"] == "cs_status"
    assert responses[2]["result"]["structuredContent"]["ok"] is True
    assert responses[2]["result"]["isError"] is False
    assert responses[2]["result"]["content"][0]["type"] == "text"
