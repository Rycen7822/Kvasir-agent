from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "MCP_CONTEXT_BUDGET.md"

EXPECTED_TOOLS = {
    "cs_doctor",
    "cs_status",
    "cs_context_pack",
    "cs_resume_brief",
    "cs_checkpoint",
    "cs_pack_delta",
    "cs_manifest_validate",
    "cs_trial_show",
    "cs_runner_status",
    "cs_log_digest",
    "cs_artifact_index",
    "cs_queue_status",
    "cs_queue_reconcile",
    "cs_wiki_query_pack",
    "cs_review_status",
    "cs_cost_status",
    "cs_soak_accelerated",
    "cs_soak_crash_resume",
    "cs_skill_search",
    "cs_skill_load",
}


def test_context_budget_doc_exists_and_rejects_over_compression():
    text = DOC.read_text(encoding="utf-8")
    lower = text.lower()

    assert "4K" in text and "8K" in text
    assert "12K" in text and "24K" in text
    assert "not smaller is better" in lower or "不是越小越好" in text
    assert "cs_status" in text and "cs_resume_brief" in text and "cs_checkpoint" in text
    assert "cs_pack_delta" in text and "cs_log_digest" in text and "cs_artifact_index" in text
    assert "allow_full=true" in text
    assert "raw logs" in lower
    assert "full artifact" in lower
    assert "source_refs" in text
    assert "next_action" in text


def test_docs_list_current_twenty_tool_surface_and_no_all_tools_mcp():
    docs = "\n".join(
        (ROOT / "docs" / name).read_text(encoding="utf-8")
        for name in ("MCP.md", "USAGE.md", "ARCHITECTURE.md", "LONG_RUN.md", "MCP_CONTEXT_BUDGET.md")
    )
    for tool in EXPECTED_TOOLS:
        assert tool in docs
    assert "all-tools/full-runtime MCP" in docs
    assert "20" in (ROOT / "docs" / "MCP.md").read_text(encoding="utf-8")


def test_long_run_doc_names_recovery_artifacts_and_validation_limits():
    text = (ROOT / "docs" / "LONG_RUN.md").read_text(encoding="utf-8")
    assert "events.lock" in text
    assert "heartbeat.txt" in text
    assert "exit_code.txt" in text
    assert "cs_resume_brief" in text
    assert "cs_checkpoint" in text
    assert "cs_log_digest" in text
    assert "cs_artifact_index" in text
    assert "failed_artifact" in text
    assert "missing_heartbeat" in text
    assert "wall-clock: not_run" in text
