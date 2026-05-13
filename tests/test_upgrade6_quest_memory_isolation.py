from __future__ import annotations

from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, payload
    return payload


def _new_quest(tmp_path: Path, title: str) -> str:
    payload = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": title, "title": title}))
    return str(payload["quest"]["quest_id"])


def test_memory_requires_quest_id_and_never_falls_back_to_global(tmp_path: Path):
    calls = [
        ("cs_memory_write", {"project": str(tmp_path), "title": "global leak", "content": "must not write"}),
        ("cs_memory_search", {"project": str(tmp_path), "query": "global leak"}),
        ("cs_memory_list_recent", {"project": str(tmp_path)}),
        ("cs_memory_read", {"project": str(tmp_path), "card_id": "missing"}),
    ]

    for tool_name, args in calls:
        payload = call_tool(tool_name, args)
        assert payload.get("ok") is False, (tool_name, payload)
        assert payload.get("error_type") in {"missing_argument", "unsupported_scope", "not_found"}, payload

    assert not (tmp_path / "CodexScientist" / "home" / "memory").exists()
    assert not (tmp_path / "CodexScientist" / "memory").exists()


def test_quest_memory_isolated_between_quests(tmp_path: Path):
    q1 = _new_quest(tmp_path, "Quest One")
    q2 = _new_quest(tmp_path, "Quest Two")

    written = _ok(
        call_tool(
            "cs_memory_write",
            {
                "project": str(tmp_path),
                "quest_id": q1,
                "kind": "idea",
                "title": "unique q1 idea",
                "content": "unique-token-q1-only",
            },
        )
    )
    assert written.get("quest_id") == q1
    assert written.get("scope") == "quest"

    q2_search = _ok(call_tool("cs_memory_search", {"project": str(tmp_path), "quest_id": q2, "query": "unique-token-q1-only"}))
    assert q2_search.get("quest_id") == q2
    assert q2_search.get("matches") == []

    for scope in ("global", "both"):
        payload = call_tool("cs_memory_search", {"project": str(tmp_path), "quest_id": q1, "query": "unique", "scope": scope})
        assert payload.get("ok") is False, payload
        assert payload.get("error_type") == "unsupported_scope", payload
