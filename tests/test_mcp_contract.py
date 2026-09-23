from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def smoke(*args: str) -> dict:
    completed = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "ka_mcp.py"), "--stdio-smoke", *args],
        cwd=PLUGIN_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(completed.stdout)


def test_mcp_tool_registry_is_curated_ka_only():
    from kvasir_agent.mcp.tool_registry import list_tool_specs

    core_tools = list_tool_specs()
    core_names = [tool.name for tool in core_tools]
    evidence_names = [tool.name for tool in list_tool_specs("evidence")]
    goal_names = [tool.name for tool in list_tool_specs("goal")]
    assert "ka_doctor" in core_names
    assert "ka_tool_schema" in core_names
    assert "ka_manifest_validate" not in core_names
    assert "ka_queue_status" not in core_names
    assert "ka_goal_state" not in core_names
    assert "ka_goal_next_action" not in core_names
    assert "ka_manifest_validate" in evidence_names
    assert "ka_queue_status" not in evidence_names
    assert set(goal_names) == set(evidence_names)
    assert all(name.startswith("ka_") for name in evidence_names)
    assert not any(name.startswith("d" + "s_") or name.startswith("kvasiragent_") for name in evidence_names)
    assert len(core_names) <= 12
    assert len(evidence_names) < 48


def test_mcp_stdio_smoke_initialize_list_and_call_doctor():
    init = smoke("initialize")
    assert init["ok"] is True
    assert init["server"] == "ka_mcp"

    listed = smoke("tools/list")
    names = [tool["name"] for tool in listed["tools"]]
    assert "ka_doctor" in names
    assert "ka_tool_schema" in names
    assert all(name.startswith("ka_") for name in names)

    doctor = smoke("call", "ka_doctor", "{}")
    assert doctor["ok"] is True
    assert doctor["transport"] == "kvasir-agent-mcp"
    assert doctor["tool"] == "ka_doctor"


def test_mcp_stdio_jsonrpc_initialize_list_and_call_status():
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ka_status", "arguments": {}}},
    ]
    completed = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "ka_mcp.py")],
        cwd=PLUGIN_ROOT,
        input="\n".join(json.dumps(message) for message in messages) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]

    assert [response["id"] for response in responses] == [1, 2, 3]
    assert responses[0]["result"]["server"] == "ka_mcp"
    assert responses[0]["result"]["protocolVersion"]
    assert responses[0]["result"]["serverInfo"]["name"] == "ka_mcp"
    assert "tools" in responses[0]["result"]["capabilities"]
    tools = responses[1]["result"]["tools"]
    assert "ka_status" in [tool["name"] for tool in tools]
    assert all("inputSchema" in tool for tool in tools)
    assert responses[2]["result"]["ok"] is True
    assert responses[2]["result"]["tool"] == "ka_status"
    assert responses[2]["result"]["structuredContent"]["ok"] is True
    assert responses[2]["result"]["isError"] is False
    assert responses[2]["result"]["content"][0]["type"] == "text"
