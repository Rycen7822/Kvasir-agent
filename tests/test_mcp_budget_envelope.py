from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def test_redaction_preserves_budget_token_fields_but_redacts_real_tokens():
    payload = redact_payload({"tokens_estimate": 123, "max_tokens": 256, "access_token": "supersecret", "nested": {"token": "hunter2"}})

    assert payload["tokens_estimate"] == 123
    assert payload["max_tokens"] == 256
    assert payload["access_token"] == "[REDACTED]"
    assert payload["nested"]["token"] == "[REDACTED]"
