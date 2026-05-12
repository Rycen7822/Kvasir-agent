from __future__ import annotations

from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def test_related_work_refs_are_required_for_novelty_contract(tmp_path: Path):
    payload = call_tool(
        "cs_submit_idea",
        {
            "project": str(tmp_path),
            "quest_id": "QREL",
            "idea_id": "I-no-related-work",
            "title": "ungrounded novelty",
            "hypothesis": "h",
            "mechanism": "new mechanism",
            "novelty_contract": {
                "mechanism": "new mechanism",
                "related_work_refs": [],
                "expected_difference": "not grounded",
            },
        },
    )
    assert payload["ok"] is False
    assert payload["error_type"] == "missing_related_work_refs"
    assert payload["recoverable"] is True
