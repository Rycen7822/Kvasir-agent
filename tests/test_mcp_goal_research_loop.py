from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _assert_ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def test_goal_research_loop_runs_through_mcp_without_cli(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEXSCIENTIST_PROJECT_ROOT", str(tmp_path))

    quest = _assert_ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "tiny mcp loop", "title": "Tiny MCP Loop"}))
    quest_id = quest["quest"]["quest_id"]

    requirement = _assert_ok(
        call_tool(
            "cs_record_user_requirement",
            {"project": str(tmp_path), "quest_id": quest_id, "message": "Use only deterministic toy artifacts.", "stage": "scout"},
        )
    )
    assert requirement["quest_id"] == quest_id

    baseline = _assert_ok(
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
    confirm_args = {"project": str(tmp_path), **baseline["confirm_args"]}
    _assert_ok(call_tool("cs_confirm_baseline", confirm_args))

    idea = _assert_ok(
        call_tool(
            "cs_submit_idea",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "title": "Toy idea",
                "problem": "Need a deterministic smoke idea.",
                "hypothesis": "A recorded stub is enough for MCP loop verification.",
                "mechanism": "Record structured metadata without running external code.",
                "expected_gain": "Completes P4-2 tool loop.",
                "risks": ["toy-only"],
                "decision_reason": "Smoke test",
                "next_target": "analysis",
                "novelty_contract": {
                    "mechanism": "Record structured metadata without running external code.",
                    "related_work_refs": ["toy-baseline"],
                    "expected_difference": "records MCP loop metadata without external execution",
                    "risk_notes": ["toy-only"],
                },
            },
        )
    )
    assert idea.get("ok") is True

    experiment = _assert_ok(
        call_tool(
            "cs_record_main_experiment",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "run_id": "toy-run-1",
                "title": "Toy deterministic experiment",
                "hypothesis": "Recorded-only experiment can exercise MCP bridge.",
                "setup": "No external execution.",
                "execution": "MCP call only.",
                "results": "metric=1.0",
                "conclusion": "Bridge works.",
                "metric_rows": [{"metric": "primary", "value": 1.0}],
                "metrics_summary": {"primary": 1.0},
                "evidence_paths": [],
                "verdict": "candidate",
            },
        )
    )
    assert experiment.get("ok") is True

    campaign = _assert_ok(
        call_tool(
            "cs_create_analysis_campaign",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "campaign_title": "Toy analysis",
                "campaign_goal": "Check deterministic loop evidence.",
                "slices": [{"slice_id": "S1", "question": "Does MCP loop record?"}],
            },
        )
    )
    campaign_id = campaign.get("campaign_id") or campaign.get("campaign", {}).get("campaign_id") or "active"

    slice_payload = _assert_ok(
        call_tool(
            "cs_record_analysis_slice",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "campaign_id": campaign_id,
                "slice_id": "S1",
                "status": "completed",
                "setup": "Toy setup",
                "execution": "Recorded analysis only",
                "results": "No CLI was needed.",
            },
        )
    )
    assert slice_payload.get("ok") is True

    _assert_ok(call_tool("cs_get_method_scoreboard", {"project": str(tmp_path), "quest_id": quest_id}))
    _assert_ok(call_tool("cs_get_optimization_frontier", {"project": str(tmp_path), "quest_id": quest_id}))
    checkpoint = _assert_ok(
        call_tool(
            "cs_checkpoint",
            {
                "project": str(tmp_path),
                "phase": "p4-2-toy-loop",
                "completed": ["mcp-loop"],
                "next_action": "continue",
            },
        )
    )
    resume = _assert_ok(call_tool("cs_resume_brief", {"project": str(tmp_path), "max_chars": 4000}))

    assert checkpoint.get("checkpoint_id") or checkpoint.get("checkpoint")
    assert "resume" in json.dumps(resume, ensure_ascii=False).lower() or resume.get("text")

    repo_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in tmp_path.rglob("*.json") if path.is_file())
    assert "scripts/csctl.py" not in repo_text
