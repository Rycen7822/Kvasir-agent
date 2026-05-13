from __future__ import annotations

from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, payload
    return payload


def _confirm_baseline(tmp_path: Path, quest_id: str) -> None:
    baseline = _ok(
        call_tool(
            "cs_create_local_baseline",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "baseline_id": "toy_baseline",
                "summary": "Toy deterministic baseline.",
                "overwrite": True,
            },
        )
    )
    _ok(call_tool("cs_confirm_baseline", {"project": str(tmp_path), **baseline["confirm_args"]}))


def test_main_experiment_records_evidence_without_method_planner_gate(tmp_path: Path):
    quest = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "method ledger", "title": "Method Ledger"}))
    quest_id = quest["quest"]["quest_id"]
    _confirm_baseline(tmp_path, quest_id)
    _ok(
        call_tool(
            "cs_submit_idea",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "title": "Regressing idea",
                "hypothesis": "h",
                "mechanism": "widening layer blindly",
                "novelty_contract": {
                    "mechanism": "widening layer blindly",
                    "related_work_refs": ["paper-a"],
                    "expected_difference": "wider layer changes optimization behavior",
                    "risk_notes": ["may regress"],
                },
            },
        )
    )

    recorded = _ok(
        call_tool(
            "cs_record_main_experiment",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "run_id": "R-METHOD",
                "title": "toy run",
                "hypothesis": "h",
                "metric_rows": [{"metric": "primary", "value": 0.3, "baseline": 0.5}],
                "evidence_paths": ["artifacts/metrics.json"],
                "verdict": "regressed",
            },
        )
    )
    assert "method_improvement_due" not in recorded
    assert "next_required_tool" not in recorded

    updated = _ok(
        call_tool(
            "cs_update_method_scoreboard",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "idea_id": "I-regressed",
                "outcome": "negative",
                "metric_delta": -0.2,
                "lesson": "avoid widening layer blindly",
                "mechanism": "widening layer blindly",
            },
        )
    )
    assert updated["scoreboard"]["ideas"]["I-regressed"]["outcome"] == "negative"
    assert updated["recorded_negative_memory"] is True

    state_path = tmp_path / "CodexScientist" / "quests" / quest_id / "runtime" / "goal_state.json"
    if state_path.exists():
        assert "cs_select_next_idea" not in state_path.read_text(encoding="utf-8")
