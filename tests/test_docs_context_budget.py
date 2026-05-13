from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "MCP_CONTEXT_BUDGET.md"

EXPECTED_TOOLS = {
    "cs_doctor",
    "cs_status",
    "cs_tool_schema",
    "cs_new_quest",
    "cs_record_user_requirement",
    "cs_context_pack",
    "cs_resume_brief",
    "cs_checkpoint",
    "cs_pack_delta",
    "cs_create_local_baseline",
    "cs_confirm_baseline",
    "cs_submit_idea",
    "cs_record_main_experiment",
    "cs_create_analysis_campaign",
    "cs_record_analysis_slice",
    "cs_log_digest",
    "cs_artifact_index",
    "cs_claim_gate",
}


def test_context_budget_doc_exists_and_rejects_over_compression():
    text = DOC.read_text(encoding="utf-8")
    lower = text.lower()

    assert "4K" in text and "8K" in text
    assert "12K" in text and "24K" in text
    assert "not smaller is better" in lower or "不是越小越好" in text
    assert "cs_status" in text and "cs_resume_brief" in text and "cs_checkpoint" in text
    assert "cs_pack_delta" in text and "cs_log_digest" in text and "cs_artifact_index" in text
    assert "raw logs" in lower
    assert "full artifact" in lower
    assert "source_refs" in text
    assert "validation" in text


def test_docs_list_current_p4_profiles_and_no_all_tools_mcp():
    docs = "\n".join(
        (ROOT / "docs" / name).read_text(encoding="utf-8")
        for name in ("MCP.md", "USAGE.md", "ARCHITECTURE.md", "LONG_RUN.md", "MCP_CONTEXT_BUDGET.md")
    )
    for tool in EXPECTED_TOOLS:
        assert tool in docs
    assert "all-tools/full-runtime MCP" in docs
    assert "default core profile has 11 tools" in docs
    assert "evidence" in docs and "formal_run" in docs and "literature" in docs and "paper_write" in docs
    assert "stage` argument is a context label" in docs or "`stage` is a label" in docs
    for stale in ["core profile: 14 tools", "goal profile: 47 tools", "active stage subset"]:
        assert stale not in docs


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
