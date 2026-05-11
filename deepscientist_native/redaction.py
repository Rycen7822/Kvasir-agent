"""Secret redaction helpers for DeepScientist plugin outputs."""

from __future__ import annotations

import json
import re
from typing import Any

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|password|passwd|secret|authorization|cookie)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_URL_CREDENTIALS = re.compile(r"(://[^:/\s]+:)([^@/\s]+)(@)")


def redact_text(value: str) -> str:
    text = str(value)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    text = _URL_CREDENTIALS.sub(r"\1[REDACTED]\3", text)
    return text


def redact_payload(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if re.search(r"(?i)(api[_-]?key|token|password|passwd|secret|authorization|cookie)", str(key)):
                redacted[str(key)] = "[REDACTED]" if item is not None else None
            else:
                redacted[str(key)] = redact_payload(item)
        return redacted
    return value


def dumps_json(payload: dict[str, Any]) -> str:
    return json.dumps(redact_payload(payload), ensure_ascii=False, indent=2)
