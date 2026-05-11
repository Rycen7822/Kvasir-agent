from __future__ import annotations

from typing import Any

# Hermes-headless backend keeps generic conversation identity helpers because
# quest state still needs stable local conversation keys.
# This module intentionally contains no social connector runtime, network
# bridge, channel registration, or delivery logic.

PROFILE_CHAT_ID_SEPARATOR = "::"


def _decode_chat_id(chat_id: str) -> tuple[str | None, str]:
    if PROFILE_CHAT_ID_SEPARATOR not in chat_id:
        return None, chat_id
    profile_id, resolved_chat_id = chat_id.split(PROFILE_CHAT_ID_SEPARATOR, 1)
    normalized_profile_id = str(profile_id or "").strip() or None
    normalized_chat_id = str(resolved_chat_id or "").strip() or chat_id
    return normalized_profile_id, normalized_chat_id


def encode_chat_id(chat_id: Any, *, profile_id: Any = None) -> str:
    normalized_chat_id = str(chat_id or "").strip()
    if not normalized_chat_id:
        return ""
    normalized_profile_id = str(profile_id or "").strip()
    if not normalized_profile_id:
        return normalized_chat_id
    return f"{normalized_profile_id}{PROFILE_CHAT_ID_SEPARATOR}{normalized_chat_id}"


def format_conversation_id(source: str, chat_type: str, chat_id: Any, *, profile_id: Any = None) -> str:
    normalized_source = str(source or "").strip().lower()
    normalized_chat_type = str(chat_type or "").strip().lower()
    encoded_chat_id = encode_chat_id(chat_id, profile_id=profile_id)
    return f"{normalized_source}:{normalized_chat_type}:{encoded_chat_id}"


def parse_conversation_id(conversation_id: Any) -> dict[str, str] | None:
    raw = str(conversation_id or "").strip()
    parts = raw.split(":", 2)
    if len(parts) != 3:
        return None
    source, chat_type, chat_id = parts
    if not source or not chat_type or not chat_id:
        return None
    profile_id, resolved_chat_id = _decode_chat_id(chat_id)
    return {
        "conversation_id": raw,
        "connector": source,
        "source": source,
        "chat_type": chat_type,
        "chat_id": resolved_chat_id,
        "chat_id_raw": chat_id,
        "profile_id": profile_id or "",
    }


def normalize_conversation_id(conversation_id: Any) -> str:
    raw = str(conversation_id or "").strip()
    if not raw:
        return "local:default"
    lowered = raw.lower()
    if lowered in {"web", "cli", "api", "command", "local", "local-ui", "tui-ink", "tui-textual", "web-react", "tui-local"}:
        return "local:default"
    parsed = parse_conversation_id(raw)
    if parsed is not None:
        return format_conversation_id(
            parsed["source"].lower(),
            parsed["chat_type"].lower(),
            parsed["chat_id"],
            profile_id=parsed.get("profile_id") or None,
        )
    if ":" in raw:
        return raw
    return f"{lowered}:default"


def conversation_identity_key(conversation_id: Any) -> str:
    normalized = normalize_conversation_id(conversation_id)
    parsed = parse_conversation_id(normalized)
    if parsed is None:
        return normalized.lower()
    profile_key = str(parsed.get("profile_id") or "").strip().lower()
    return ":".join(
        item
        for item in (
            parsed["source"].lower(),
            profile_key,
            parsed["chat_type"].lower(),
            parsed["chat_id"].lower(),
        )
        if item
    )
