from __future__ import annotations

import json
from pathlib import Path

from kvasir_agent.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, payload
    return payload


def _confirm_baseline(tmp_path: Path, quest_id: str) -> None:
    baseline = _ok(
        call_tool(
            "ka_create_local_baseline",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "baseline_id": "toy_baseline",
                "summary": "Toy deterministic baseline.",
                "overwrite": True,
            },
        )
    )
    _ok(call_tool("ka_confirm_baseline", {"project": str(tmp_path), **baseline["confirm_args"]}))


def test_submit_idea_requires_novelty_contract(tmp_path: Path):
    missing = call_tool("ka_submit_idea", {"project": str(tmp_path), "quest_id": "QNOV", "title": "new idea"})
    assert missing["ok"] is False
    assert missing["error_type"] == "missing_novelty_contract"
    assert "novelty_contract" in missing["required_fields"]


def test_submit_idea_persists_contract_without_fabricated_scores(tmp_path: Path):
    quest = _ok(call_tool("ka_new_quest", {"project": str(tmp_path), "goal": "novelty gate", "title": "Novelty Gate"}))
    quest_id = quest["quest"]["quest_id"]
    _confirm_baseline(tmp_path, quest_id)
    payload = call_tool(
        "ka_submit_idea",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "idea_id": "I-novel",
            "title": "new idea",
            "hypothesis": "h",
            "mechanism": "adaptive evidence routing",
            "novelty_contract": {
                "mechanism": "adaptive evidence routing",
                "related_work_refs": ["paper-a"],
                "expected_difference": "routes evidence before paper claims",
                "risk_notes": ["small toy validation"],
                "selection_scores": {"novelty": 0.99},
            },
        },
    )
    assert payload["ok"] is True, payload
    assert payload["assessment_status"] == "not_assessed"
    assert "method_scores" not in payload
    assert "selection_scores" not in payload["novelty_contract"]
    stored = json.loads(Path(payload["path"]).read_text())
    assert stored["novelty_contract"] == payload["novelty_contract"]
    assert stored["assessment_status"] == "not_assessed"
    assert "selection_scores" not in stored
