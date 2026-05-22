from __future__ import annotations

from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, payload
    return payload


def _new_quest(tmp_path: Path, title: str) -> str:
    payload = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": title, "title": title}))
    return str(payload["quest"]["quest_id"])


def test_memory_read_paths_without_state_fail_closed_and_never_fall_back_to_global(tmp_path: Path):
    calls = [
        ("cs_memory_search", {"project": str(tmp_path), "query": "global leak"}),
        ("cs_memory_list_recent", {"project": str(tmp_path)}),
        ("cs_memory_read", {"project": str(tmp_path), "card_id": "missing"}),
    ]

    for tool_name, args in calls:
        payload = call_tool(tool_name, args)
        assert payload.get("ok") is False, (tool_name, payload)
        assert payload.get("error_type") in {"no_research_state", "unsupported_scope", "not_found"}, payload

    assert not (tmp_path / "CodexScientist" / "home" / "memory").exists()
    assert not (tmp_path / "CodexScientist" / "memory").exists()


def test_memory_write_without_quest_id_lazily_creates_root_bound_memory(tmp_path: Path):
    written = _ok(
        call_tool(
            "cs_memory_write",
            {
                "project": str(tmp_path),
                "title": "root-bound memory",
                "content": "first durable write creates project-local state",
                "kind": "decision",
            },
        )
    )

    state_root = tmp_path / "CodexScientist"
    card_path = Path(str(written["card"]["path"]))
    assert written.get("scope") == "quest"
    assert written.get("quest_root") == str(state_root)
    assert card_path.is_relative_to(state_root / "memory")
    assert (state_root / "research.yaml").exists()
    assert not (state_root / "quests").exists()


def test_root_bound_memory_uses_single_manifest_provenance_without_identity_switching(tmp_path: Path):
    q1 = _new_quest(tmp_path, "Quest One")
    q2 = _new_quest(tmp_path, "Quest Two")
    assert q2 == q1

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

    same_research_search = _ok(call_tool("cs_memory_search", {"project": str(tmp_path), "quest_id": q2, "query": "unique-token-q1-only"}))
    assert same_research_search.get("quest_id") == q1
    assert same_research_search.get("matches")

    mismatch = call_tool("cs_memory_search", {"project": str(tmp_path), "quest_id": "different-quest", "query": "unique-token-q1-only"})
    assert mismatch.get("ok") is False, mismatch
    assert mismatch.get("error_type") == "root_bound_quest_id_mismatch", mismatch

    for scope in ("global", "both"):
        payload = call_tool("cs_memory_search", {"project": str(tmp_path), "quest_id": q1, "query": "unique", "scope": scope})
        assert payload.get("ok") is False, payload
        assert payload.get("error_type") == "unsupported_scope", payload
