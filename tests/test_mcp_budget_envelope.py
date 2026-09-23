from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kvasir_agent.mcp.envelope import apply_budget_envelope
from kvasir_agent.mcp.tool_registry import call_tool
from kvasir_agent.runtime.redaction import redact_payload

_REQUIRED_ENVELOPE_KEYS = {
    "schema_version",
    "summary",
    "content",
    "omitted_fields",
    "tokens_estimate",
    "chars",
    "truncated",
    "source_refs",
    "next_call",
    "warnings",
}


def _assert_budget_envelope(payload: dict[str, Any]) -> None:
    missing = _REQUIRED_ENVELOPE_KEYS - set(payload)
    assert not missing, f"missing budget envelope keys: {sorted(missing)} in {payload}"
    assert isinstance(payload["tokens_estimate"], int)
    assert payload["tokens_estimate"] >= 0
    assert isinstance(payload["chars"], int)
    assert payload["chars"] >= 0
    assert isinstance(payload["truncated"], bool)
    assert isinstance(payload["source_refs"], list)
    assert payload["next_call"] is None or isinstance(payload["next_call"], dict)
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["schema_version"], int)
    assert isinstance(payload["summary"], str)
    assert "content" in payload
    assert isinstance(payload["omitted_fields"], list)


def test_status_and_recovery_tools_use_uniform_budget_envelope(tmp_path: Path):
    payloads = [
        call_tool("ka_status", {"project": str(tmp_path)}),
        call_tool("ka_queue_status", {"project": str(tmp_path), "limit": 5}),
        call_tool("ka_runner_status", {"project": str(tmp_path)}),
        call_tool("ka_resume_brief", {"project": str(tmp_path)}),
    ]
    for payload in payloads:
        _assert_budget_envelope(payload)
        rendered = json.dumps(payload, ensure_ascii=False)
        assert "supersecret" not in rendered
        assert "hunter2" not in rendered


def test_error_tool_payloads_use_budget_envelope_and_redaction():
    sensitive_text = "tok" + "en=" + "supersecret" + " pass" + "word=" + "hunter2"

    payloads = [
        call_tool("ka_missing_" + sensitive_text, {}),
        call_tool("ka_queue_status", {"limit": sensitive_text}),
    ]

    for payload in payloads:
        assert payload["ok"] is False
        assert payload["recoverable"] is True
        _assert_budget_envelope(payload)
        rendered = json.dumps(payload, ensure_ascii=False)
        assert "supersecret" not in rendered
        assert "hunter2" not in rendered
        assert "[REDACTED]" in rendered


def test_budget_envelope_redacts_warning_and_source_ref_values():
    payload = apply_budget_envelope(
        {
            "ok": True,
            "warnings": ["token=" + "supersecret"],
            "source_refs": [{"path": "/tmp/password=" + "hunter2"}],
        },
        tool_name="ka_status",
    )

    _assert_budget_envelope(payload)
    rendered = json.dumps(payload, ensure_ascii=False)
    assert "supersecret" not in rendered
    assert "hunter2" not in rendered
    assert "[REDACTED]" in rendered


def test_redaction_preserves_budget_token_fields_but_redacts_real_tokens():
    payload = redact_payload({"tokens_estimate": 123, "max_tokens": 256, "access_token": "supersecret", "nested": {"token": "hunter2"}})

    assert payload["tokens_estimate"] == 123
    assert payload["max_tokens"] == 256
    assert payload["access_token"] == "[REDACTED]"
    assert payload["nested"]["token"] == "[REDACTED]"
