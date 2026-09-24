from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_cli_envelope_redacts_secret_like_values():
    from kvasir_agent.adapters.cli import normalize_envelope

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
