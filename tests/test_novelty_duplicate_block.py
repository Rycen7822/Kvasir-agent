from __future__ import annotations

from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def test_duplicate_mechanism_is_blocked_by_negative_memory(tmp_path: Path):
    recorded = call_tool(
        "cs_record_negative_result",
        {
            "project": str(tmp_path),
            "quest_id": "QDUP",
            "trial_id": "T-old",
            "idea_id": "I-old",
            "failure_reason": "regressed",
            "lesson": "avoid widening layer blindly",
            "mechanism": "widening layer blindly",
        },
    )
    assert recorded["ok"] is True, recorded

    duplicate = call_tool(
        "cs_submit_idea",
        {
            "project": str(tmp_path),
            "quest_id": "QDUP",
            "idea_id": "I-new",
            "title": "duplicate",
            "hypothesis": "h",
            "mechanism": "widening layer blindly",
            "novelty_contract": {
                "mechanism": "widening layer blindly",
                "related_work_refs": ["paper-a"],
                "expected_difference": "same failed mechanism",
                "risk_notes": ["known negative"],
            },
        },
    )
    assert duplicate["ok"] is False
    assert duplicate["error_type"] == "duplicate_negative_memory"
    assert duplicate["similar_failed_ideas"] == ["I-old"]
