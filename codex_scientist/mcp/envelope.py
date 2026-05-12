"""MCP payload envelope helpers for bounded CodexScientist tool output."""
from __future__ import annotations

import json
from typing import Any

from codex_scientist.adapters.cli import normalize_envelope

_BUDGET_KEYS = {"tokens_estimate", "chars", "truncated", "source_refs", "next_call", "warnings"}


def _json_len(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def _as_warning_list(value: Any, *, truncated: bool) -> list[str]:
    warnings: list[str] = []
    if isinstance(value, list):
        warnings.extend(str(item) for item in value if str(item))
    elif isinstance(value, str) and value:
        warnings.append(value)
    if truncated and "output_truncated_to_budget" not in warnings:
        warnings.append("output_truncated_to_budget")
    return warnings


def _as_source_refs(value: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                refs.append(dict(item))
            elif item:
                refs.append({"path": str(item)})
    for key in ("source_path", "context_pack_path", "log_path", "artifact_path"):
        item = payload.get(key)
        if item and all(ref.get("path") != str(item) for ref in refs):
            refs.append({"path": str(item), "kind": key})
    return refs


def _default_next_call(tool_name: str | None, payload: dict[str, Any]) -> dict[str, str] | None:
    existing = payload.get("next_call")
    if isinstance(existing, dict):
        return {str(key): str(value) for key, value in existing.items()}
    if not payload.get("ok", True):
        reason = str(payload.get("suggested_next_action") or "recover from MCP error")
        return {"tool": "tools/list", "reason": reason}
    if tool_name == "cs_skill_search":
        return {"tool": "cs_skill_load", "reason": "load one bounded skill view from a returned handle"}
    if tool_name in {"cs_status", "cs_queue_status", "cs_runner_status"}:
        return {"tool": "cs_context_pack", "reason": "build a bounded state pack before long-running reasoning"}
    return None


def _summary(tool_name: str | None, payload: dict[str, Any]) -> str:
    existing = payload.get("summary")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    if not payload.get("ok", True):
        return str(payload.get("error") or f"{tool_name or 'tool'} failed")[:240]
    return f"{tool_name or payload.get('tool') or 'tool'} completed"


def _omitted_fields(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def apply_budget_envelope(payload: dict[str, Any], *, tool_name: str | None = None) -> dict[str, Any]:
    """Return a redacted MCP payload with stable budget metadata.

    The helper deliberately does not truncate payload bodies. Individual services
    still own content budgeting. This layer records bounded-output metadata and
    makes every success/error payload expose the same recovery anchors.
    """
    staged = dict(payload)
    if tool_name is not None:
        staged.setdefault("tool", tool_name)
    staged.setdefault("transport", "codexscientist-mcp")
    staged.setdefault("mcp", True)

    original_tokens = staged.get("tokens_estimate") if isinstance(staged.get("tokens_estimate"), int) else None
    original_chars = staged.get("chars") if isinstance(staged.get("chars"), int) else None
    original_truncated = staged.get("truncated") if isinstance(staged.get("truncated"), bool) else False

    normalized = normalize_envelope(staged)
    refs = _as_source_refs(normalized.get("source_refs"), normalized)
    warnings = _as_warning_list(normalized.get("warnings"), truncated=original_truncated)
    schema_version = normalized.get("schema_version") if isinstance(normalized.get("schema_version"), int) else 1
    summary = _summary(tool_name, normalized)
    content = normalized.get("content") if "content" in normalized else None
    omitted_fields = _omitted_fields(normalized.get("omitted_fields"))

    without_budget = {key: value for key, value in normalized.items() if key not in _BUDGET_KEYS}
    chars = original_chars if original_chars is not None else _json_len(without_budget)
    tokens_estimate = original_tokens if original_tokens is not None else (chars + 3) // 4

    normalized["schema_version"] = schema_version
    normalized["summary"] = summary
    normalized["content"] = content
    normalized["omitted_fields"] = omitted_fields
    normalized["tokens_estimate"] = tokens_estimate
    normalized["chars"] = chars
    normalized["truncated"] = original_truncated
    normalized["source_refs"] = refs
    normalized["next_call"] = _default_next_call(tool_name, normalized)
    normalized["warnings"] = warnings
    return normalized
