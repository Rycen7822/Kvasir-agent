from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_ctl(script_name: str, *args: str, allow_error: bool = False) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / script_name), *args],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if allow_error:
        assert proc.stdout.strip(), proc.stderr
    else:
        assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_csctl_exists_and_matches_dsctl_public_tool_envelope():
    assert (PLUGIN_ROOT / "scripts" / "csctl.py").exists()

    csctl_payload = run_ctl("csctl.py", "list-tools", "--format", "json")
    dsctl_payload = run_ctl("dsctl.py", "list-tools", "--format", "json")

    assert csctl_payload["ok"] is True
    assert csctl_payload["transport"] == "codex-native-cli"
    assert csctl_payload["mcp"] is False
    assert csctl_payload["count"] == dsctl_payload["count"]
    assert {item["name"] for item in csctl_payload["tools"]} == {item["name"] for item in dsctl_payload["tools"]}


def assert_unknown_tool_envelope(payload: dict) -> None:
    assert payload["ok"] is False
    assert payload["transport"] == "codex-native-cli"
    assert payload["mcp"] is False
    assert payload["error"]
    assert payload["error_type"] == "unknown_tool"
    assert payload["recoverable"] is True


def test_csctl_error_envelope_is_stable_json():
    payload = run_ctl("csctl.py", "call", "missing_tool", "--format", "json", allow_error=True)
    assert_unknown_tool_envelope(payload)


def test_dsctl_error_envelope_matches_csctl_for_unknown_tool():
    csctl_payload = run_ctl("csctl.py", "call", "missing_tool", "--format", "json", allow_error=True)
    dsctl_payload = run_ctl("dsctl.py", "call", "missing_tool", "--format", "json", allow_error=True)

    assert_unknown_tool_envelope(dsctl_payload)
    assert {key: dsctl_payload[key] for key in ("ok", "transport", "mcp", "error_type", "recoverable")} == {
        key: csctl_payload[key] for key in ("ok", "transport", "mcp", "error_type", "recoverable")
    }


def test_legacy_dsctl_adapter_delegates_to_native_cli_envelope():
    from codex_scientist.adapters.legacy_dsctl import run

    payload = run(["call", "missing_tool"])
    assert_unknown_tool_envelope(payload)


def test_cli_envelope_redacts_secret_like_values():
    from codex_scientist.adapters.cli import normalize_envelope

    payload = normalize_envelope(
        {
            "ok": False,
            "error": "token=sk-test password=abc Authorization: Bearer secret-token",
            "details": {"api_key": "sk-test", "nested": "cookie=session-token"},
        }
    )

    rendered = json.dumps(payload, ensure_ascii=False)
    assert "sk-test" not in rendered
    assert "secret-token" not in rendered
    assert "session-token" not in rendered
    assert "[REDACTED]" in rendered
