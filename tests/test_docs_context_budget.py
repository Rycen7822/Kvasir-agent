from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "MCP_CONTEXT_BUDGET.md"

EXPECTED_TOOLS = {
    "ka_doctor",
    "ka_status",
    "ka_tool_schema",
    "ka_record_user_requirement",
    "ka_context_pack",
    "ka_resume_brief",
    "ka_checkpoint",
    "ka_pack_delta",
    "ka_create_local_baseline",
    "ka_confirm_baseline",
    "ka_submit_idea",
    "ka_record_main_experiment",
    "ka_create_analysis_campaign",
    "ka_record_analysis_slice",
    "ka_log_digest",
    "ka_artifact_index",
    "ka_claim_gate",
}


def test_context_budget_doc_exists_and_rejects_over_compression():
    text = DOC.read_text(encoding="utf-8")
    lower = text.lower()

    assert "4K" in text and "8K" in text
    assert "12K" in text and "24K" in text
    assert "not smaller is better" in lower or "不是越小越好" in text
    assert "ka_status" in text and "ka_resume_brief" in text and "ka_checkpoint" in text
    assert "ka_pack_delta" in text and "ka_log_digest" in text and "ka_artifact_index" in text
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
    assert "default core profile exposes bounded root-bound recovery tools" in docs or "default core profile exposes curated" in docs
    assert "evidence" in docs and "formal_run" in docs and "literature" in docs and "paper_write" in docs
    assert "stage` argument is a context label" in docs or "`stage` is a label" in docs
    for stale in ["core profile: 14 tools", "goal profile: 47 tools", "active stage subset"]:
        assert stale not in docs


def test_long_run_doc_names_recovery_artifacts_and_validation_limits():
    text = (ROOT / "docs" / "LONG_RUN.md").read_text(encoding="utf-8")
    assert "events.lock" in text
    assert "heartbeat.txt" in text
    assert "exit_code.txt" in text
    assert "ka_resume_brief" in text
    assert "ka_checkpoint" in text
    assert "ka_log_digest" in text
    assert "ka_artifact_index" in text
    assert "failed_artifact" in text
    assert "missing_heartbeat" in text
    assert "wall-clock: not_run" in text
