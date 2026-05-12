from __future__ import annotations

from pathlib import Path

from codex_scientist.mcp.skill_eval import evaluate_cases
from codex_scientist.mcp.skill_index import clear_skill_cache, iter_skill_cards, skill_cache_info
from codex_scientist.mcp.tool_registry import call_tool

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "skill_retrieval"


_SEARCH_FIELDS = {
    "skill_id",
    "handle",
    "title",
    "description",
    "score",
    "confidence",
    "load_decision",
    "recommended_view",
    "why_match",
    "why_maybe_not",
    "missing_requirements",
    "matched_fields",
    "risk_flags",
    "trust_level",
    "source_sha256",
    "updated_at",
    "tokens_estimate",
    "truncated",
}


def test_skill_search_returns_decision_schema_without_content():
    result = call_tool(
        "cs_skill_search",
        {
            "raw_user_request": "上下文压缩后恢复长期任务",
            "description_query": "resume checkpoint delta",
            "workflow_query": "resume brief checkpoint delta context budget",
            "limit": 3,
            "max_chars": 1400,
        },
    )

    assert result["ok"] is True
    assert result["candidates"]
    for candidate in result["candidates"]:
        assert _SEARCH_FIELDS <= set(candidate)
        assert "content" not in candidate
        assert candidate["confidence"] in {"high", "medium", "low"}
        assert candidate["load_decision"] in {"safe_to_load", "preview_first", "do_not_auto_load"}
        assert candidate["recommended_view"] in {"card", "preview", "runtime", "risk", "sections"}
        assert len(candidate["source_sha256"]) == 64


def test_runtime_view_is_procedural_not_full_skill_truncation():
    runtime = call_tool("cs_skill_load", {"skill_id": "codexscientist-codex", "view": "runtime", "max_chars": 2200})
    full = call_tool(
        "cs_skill_load",
        {"skill_id": "codexscientist-codex", "view": "full", "allow_full": True, "max_chars": 12000},
    )

    assert runtime["ok"] is True
    assert full["ok"] is True
    assert runtime["content"].startswith("Use when:")
    assert "Do not use when:" in runtime["content"]
    assert "Required context:" in runtime["content"]
    assert "---\nname:" not in runtime["content"]
    assert runtime["content"] != full["content"][: len(runtime["content"])]


def test_skill_retrieval_fixture_quality_gate_passes():
    report = evaluate_cases(
        skills_root=FIXTURE_ROOT / "skills",
        cases_path=FIXTURE_ROOT / "cases.jsonl",
    )

    assert report["case_count"] == 4
    assert report["top1_accuracy"] >= 0.85
    assert report["hit_rate_at_k"] >= 0.95
    assert report["forbidden_count"] == 0
    assert report["average_latency_ms"] < 500
    assert "mean_average_precision_at_k" in report
    assert "judged_precision_at_k" in report
    assert "missing_expected_candidates" in report
    assert "forbidden_candidates" in report
    assert report["mean_average_precision_at_k"] >= 0.85
    assert report["judged_precision_at_k"] >= 0.85


def test_missing_must_have_forces_preview_first_load_decision():
    result = call_tool(
        "cs_skill_search",
        {
            "raw_user_request": "use codexscientist-codex",
            "description_query": "codexscientist-codex",
            "workflow_query": "mcp status context pack",
            "must_have": ["nonexistent-gate"],
            "limit": 1,
            "max_chars": 1400,
        },
    )

    candidate = result["candidates"][0]
    assert candidate["missing_requirements"] == ["nonexistent-gate"]
    assert candidate["load_decision"] == "preview_first"
    assert candidate["recommended_view"] == "preview"


def test_chinese_resume_request_routes_to_codex_router_when_no_resume_skill_exists():
    result = call_tool(
        "cs_skill_search",
        {
            "raw_user_request": "上下文压缩后恢复长期实验任务",
            "description_query": "",
            "workflow_query": "",
            "limit": 1,
            "max_chars": 1400,
        },
    )

    candidate = result["candidates"][0]
    assert candidate["skill_id"] == "codexscientist-codex"
    assert candidate["confidence"] in {"high", "medium"}


def test_skill_index_cache_reuses_records_and_invalidates_on_file_change(tmp_path: Path):
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "codexscientist-cache"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("---\nname: codexscientist-cache\ndescription: first description\n---\n\n# Cache\n", encoding="utf-8")
    clear_skill_cache()

    first = iter_skill_cards(skills_root)
    second = iter_skill_cards(skills_root)
    info = skill_cache_info()
    assert first[0].description == "first description"
    assert second[0].description == "first description"
    assert info["hits"] >= 1

    skill_file.write_text("---\nname: codexscientist-cache\ndescription: second description\n---\n\n# Cache\n", encoding="utf-8")
    third = iter_skill_cards(skills_root)
    assert third[0].description == "second description"
    assert skill_cache_info()["invalidations"] >= 1


def test_tiny_budget_search_preserves_full_source_hash():
    result = call_tool(
        "cs_skill_search",
        {
            "raw_user_request": "use codexscientist-codex",
            "description_query": "codexscientist-codex",
            "workflow_query": "mcp status context pack",
            "limit": 1,
            "max_chars": 500,
        },
    )

    assert result["ok"] is True
    assert result["candidates"]
    assert len(result["candidates"][0]["source_sha256"]) == 64
