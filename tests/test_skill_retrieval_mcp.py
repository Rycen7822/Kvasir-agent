from __future__ import annotations


def test_skill_search_returns_cards_not_full_skill_content():
    from kvasir_agent.mcp.tool_registry import call_tool

    result = call_tool(
        "ka_skill_search",
        {
            "raw_user_request": "检查 trial 状态并验证 manifest",
            "description_query": "trial status manifest validate",
            "workflow_query": "show trial validate manifest queue status",
            "limit": 3,
            "max_chars": 1800,
        },
    )
    assert result["ok"] is True
    assert result["candidates"]
    assert all("content" not in candidate for candidate in result["candidates"])
    assert result["tokens_estimate"] <= 1800


def test_skill_load_rejects_forged_search_handle_and_loads_runtime_view():
    from kvasir_agent.mcp.tool_registry import call_tool

    rejected = call_tool("ka_skill_load", {"handle": "search:forged:kvasir-agent", "view": "runtime"})
    assert rejected["ok"] is False
    assert rejected["error_type"] == "invalid_handle"

    search = call_tool(
        "ka_skill_search",
        {
            "raw_user_request": "use Kvasir-agent MCP tools",
            "description_query": "kvasir agent mcp router",
            "workflow_query": "kvasir agent status context pack",
            "limit": 1,
        },
    )
    handle = search["candidates"][0]["handle"]
    loaded = call_tool("ka_skill_load", {"handle": handle, "view": "runtime", "max_chars": 2200})
    assert loaded["ok"] is True
    assert loaded["view"] == "runtime"
    assert loaded["content"]
    assert loaded["tokens_estimate"] <= 2200


def test_skill_load_full_requires_explicit_allow_full():
    from kvasir_agent.mcp.tool_registry import call_tool

    rejected = call_tool("ka_skill_load", {"skill_id": "kvasir-agent", "view": "full"})
    assert rejected["ok"] is False
    assert rejected["error_type"] == "full_view_requires_explicit_allow"

    allowed = call_tool(
        "ka_skill_load",
        {"skill_id": "kvasir-agent", "view": "full", "allow_full": True, "max_chars": 800},
    )
    assert allowed["ok"] is True
    assert allowed["view"] == "full"
    assert len(allowed["content"]) <= 800


def test_skill_load_rejects_path_traversal_and_respects_tiny_budget():
    from kvasir_agent.mcp.tool_registry import call_tool

    traversal = call_tool("ka_skill_load", {"skill_id": "../kvasir-agent", "view": "preview"})
    assert traversal["ok"] is False
    assert traversal["error_type"] == "invalid_handle"

    loaded = call_tool("ka_skill_load", {"skill_id": "kvasir-agent", "view": "runtime", "max_chars": 120})
    assert loaded["ok"] is True
    assert len(loaded["content"]) <= 120
    assert loaded["tokens_estimate"] <= 120
    assert loaded["truncated"] is True
