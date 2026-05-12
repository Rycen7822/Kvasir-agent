from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_missing_trial_and_runner_ids_return_not_found_not_traceback():
    trial = call_tool("cs_trial_show", {"trial_id": "T9999"})
    runner = call_tool("cs_runner_status", {"run_id": "R9999"})

    assert trial["ok"] is False
    assert trial["error_type"] == "not_found"
    assert runner["ok"] is False
    assert runner["error_type"] == "not_found"


def test_bad_mcp_arguments_return_recoverable_payload_not_traceback(tmp_path):
    payload = call_tool("cs_soak_accelerated", {"project": str(tmp_path), "days": "not-an-int"})

    assert payload["ok"] is False
    assert payload["recoverable"] is True
    assert payload["error_type"] in {"invalid_argument", "tool_error"}


def test_stdio_bad_arguments_keep_server_alive():
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "cs_soak_accelerated", "arguments": {"days": "bad"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "cs_status", "arguments": {}}},
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

    assert responses[0]["result"]["isError"] is True
    assert responses[0]["result"]["structuredContent"]["ok"] is False
    assert responses[1]["result"]["structuredContent"]["ok"] is True


def test_tool_error_paths_redact_secret_like_input():
    secret = " ".join(["token=" + "supersecret", "password=" + "hunter2"])

    bad_limit = call_tool("cs_queue_status", {"limit": secret})
    unknown = call_tool("cs_missing_" + secret, {})

    for payload in [bad_limit, unknown]:
        rendered = json.dumps(payload, ensure_ascii=False)
        assert payload["ok"] is False
        assert "supersecret" not in rendered
        assert "hunter2" not in rendered
        assert "[REDACTED]" in rendered


def test_stdio_tool_error_content_and_structured_content_are_redacted():
    secret = " ".join(["token=" + "supersecret", "password=" + "hunter2"])
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "cs_queue_status", "arguments": {"limit": secret}},
    }
    completed = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "cs_mcp.py")],
        cwd=PLUGIN_ROOT,
        input=json.dumps(message) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    response = json.loads(completed.stdout)
    rendered = json.dumps(response, ensure_ascii=False)

    assert response["result"]["isError"] is True
    assert "supersecret" not in rendered
    assert "hunter2" not in rendered
    assert "[REDACTED]" in rendered


def test_stdio_jsonrpc_error_messages_are_redacted():
    secret_method = "method_" + "token=" + "supersecret" + " password=" + "hunter2"
    message = {"jsonrpc": "2.0", "id": 1, "method": secret_method, "params": {}}
    completed = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "cs_mcp.py")],
        cwd=PLUGIN_ROOT,
        input=json.dumps(message) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    response = json.loads(completed.stdout)
    rendered = json.dumps(response, ensure_ascii=False)

    assert response["error"]["code"] == -32601
    assert "supersecret" not in rendered
    assert "hunter2" not in rendered
    assert "[REDACTED]" in rendered
