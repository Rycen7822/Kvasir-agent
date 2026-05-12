"""Secret redaction helpers for CodexScientist plugin outputs."""

from __future__ import annotations

import json
import re
from typing import Any

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?<![A-Za-z])(api[_-]?key|token|password|passwd|secret|authorization|cookie|connection(?:[_-]?string)?|private[_-]?key|aws[_-]?key|aws[_-]?secret[_-]?access[_-]?key|secret[_-]?access[_-]?key|client[_-]?secret|account[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_URL_CREDENTIALS = re.compile(r"(://[^:/\s]+:)([^@/\s]+)(@)")
_PRIVATE_KEY_BLOCK = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.DOTALL)
_OPENAI_TOKEN = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b")
_GITHUB_TOKEN = re.compile(r"\bgh[psuor]_[A-Za-z0-9_]{16,}\b")
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")


def redact_text(value: str) -> str:
    text = str(value)
    text = _PRIVATE_KEY_BLOCK.sub("[REDACTED PRIVATE KEY]", text)
    text = _OPENAI_TOKEN.sub("[REDACTED]", text)
    text = _GITHUB_TOKEN.sub("[REDACTED]", text)
    text = _AWS_ACCESS_KEY.sub("[REDACTED]", text)
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
            if re.search(r"(?i)(api[_-]?key|token|password|passwd|secret|authorization|cookie|connection(?:[_-]?string)?|private[_-]?key|aws[_-]?key|aws[_-]?secret[_-]?access[_-]?key|secret[_-]?access[_-]?key|client[_-]?secret|account[_-]?key)", str(key)):
                redacted[str(key)] = "[REDACTED]" if item is not None else None
            else:
                redacted[str(key)] = redact_payload(item)
        return redacted
    return value


def dumps_json(payload: dict[str, Any]) -> str:
    return json.dumps(redact_payload(payload), ensure_ascii=False, indent=2)
