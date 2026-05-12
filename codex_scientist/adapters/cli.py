from __future__ import annotations

from typing import Any

from codex_scientist.runtime.redaction import redact_payload

TRANSPORT = "codex-native-cli"
MCP_ENABLED = False


def normalize_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a stable CLI JSON envelope without changing successful payloads."""
    normalized = dict(payload)
    normalized.setdefault("ok", True)
    normalized.setdefault("transport", TRANSPORT)
    normalized.setdefault("mcp", MCP_ENABLED)
    if not normalized.get("ok", False):
        error = str(normalized.get("error") or "")
        if error.startswith("Unknown tool:"):
            normalized.setdefault("error_type", "unknown_tool")
            normalized.setdefault("recoverable", True)
        else:
            normalized.setdefault("error_type", "error")
            normalized.setdefault("recoverable", False)
    return redact_payload(normalized)
