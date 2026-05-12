from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("scripts/csctl.py", "CLI fallback")


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def run_toy_goal_research(project: Path) -> dict:
    quest = _ok(call_tool("cs_new_quest", {"project": str(project), "goal": "improve deterministic toy metric", "title": "Toy Goal E2E"}))
    quest_id = quest["quest"]["quest_id"]

    _ok(call_tool("cs_record_user_requirement", {"project": str(project), "quest_id": quest_id, "message": "Use only MCP tools and deterministic toy evidence.", "stage": "scout"}))
    _ok(call_tool("cs_goal_state", {"project": str(project), "quest_id": quest_id, "active_stage": "baseline"}))
    baseline = _ok(call_tool("cs_create_local_baseline", {"project": str(project), "quest_id": quest_id, "baseline_id": "toy_baseline", "summary": "Deterministic score = 0.50", "overwrite": True}))
    _ok(call_tool("cs_confirm_baseline", {"project": str(project), **baseline["confirm_args"]}))

    _ok(call_tool("cs_goal_state", {"project": str(project), "quest_id": quest_id, "active_stage": "idea"}))
    idea = _ok(
        call_tool(
            "cs_submit_idea",
            {
                "project": str(project),
                "quest_id": quest_id,
                "title": "Normalize toy score before update",
                "problem": "Toy metric starts below target.",
                "hypothesis": "A deterministic normalization step improves the toy score.",
                "mechanism": "normalize toy score before deterministic update",
                "expected_gain": "score improves from 0.50 to 0.62",
                "risks": ["toy-only"],
                "decision_reason": "P4 E2E smoke",
                "next_target": "experiment",
                "novelty_contract": {
                    "mechanism": "normalize toy score before deterministic update",
                    "related_work_refs": ["toy-baseline", "toy-normalization-note"],
                    "expected_difference": "uses a pre-update normalization gate in the deterministic toy loop",
                    "risk_notes": ["toy-only"],
                },
            },
        )
    )

    _ok(call_tool("cs_goal_state", {"project": str(project), "quest_id": quest_id, "active_stage": "experiment"}))
    runner = _ok(call_tool("cs_runner_start", {"project": str(project), "quest_id": quest_id, "job_id": "toy-e2e", "command": "python toy_train.py", "dry_run": True}))
    experiment = _ok(
        call_tool(
            "cs_record_main_experiment",
            {
                "project": str(project),
                "quest_id": quest_id,
                "run_id": runner["run"]["run_id"],
                "title": "Deterministic toy experiment",
                "hypothesis": "Normalization improves score.",
                "setup": "No external execution; dry-run runner plus structured MCP record.",
                "execution": "MCP-only toy flow.",
                "results": "primary=0.62 vs baseline=0.50",
                "conclusion": "Promising toy improvement.",
                "metric_rows": [{"metric": "primary", "value": 0.62, "baseline": 0.50}],
                "metrics_summary": {"primary": 0.62, "baseline_primary": 0.50},
                "evidence_paths": ["artifacts/metrics/toy_metrics.json"],
                "verdict": "promising",
            },
        )
    )
    action_after_experiment = _ok(call_tool("cs_goal_next_action", {"project": str(project), "quest_id": quest_id}))

    scoreboard = _ok(call_tool("cs_update_method_scoreboard", {"project": str(project), "quest_id": quest_id, "idea_id": "toy-normalize", "outcome": "positive", "metric_delta": 0.12, "lesson": "normalization improved deterministic toy score", "mechanism": "normalize toy score before deterministic update"}))
    selected = _ok(call_tool("cs_select_next_idea", {"project": str(project), "quest_id": quest_id}))

    campaign = _ok(call_tool("cs_create_analysis_campaign", {"project": str(project), "quest_id": quest_id, "campaign_title": "Toy evidence analysis", "campaign_goal": "Check if toy improvement is claimable.", "slices": [{"slice_id": "toy-slice-1", "question": "Is the metric backed by evidence?"}]}))
    campaign_id = campaign.get("campaign_id") or campaign.get("campaign", {}).get("campaign_id") or "active"
    _ok(call_tool("cs_record_analysis_slice", {"project": str(project), "quest_id": quest_id, "campaign_id": campaign_id, "slice_id": "toy-slice-1", "status": "completed", "setup": "Toy analysis setup", "execution": "Review structured metric row", "results": "Evidence supports only a toy claim."}))

    evidence = project / "CodexScientist" / "quests" / quest_id / "artifacts" / "metrics" / "toy_metrics.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({"primary": 0.62, "baseline": 0.50}) + "\n", encoding="utf-8")
    claim = _ok(call_tool("cs_claim_gate", {"project": str(project), "quest_id": quest_id, "claim_id": "toy-claim", "claim_text": "The toy normalization improves the deterministic toy score.", "baseline_id": "toy_baseline", "metric_contract": "primary", "evidence_paths": [str(evidence)], "analysis_slice_ids": ["toy-slice-1"], "seed_count": 3}))

    checkpoint = _ok(call_tool("cs_checkpoint", {"project": str(project), "quest_id": quest_id, "phase": "toy-e2e", "completed": ["baseline", "idea", "experiment", "method-improvement", "analysis", "claim-gate"], "decisions": ["claim limited to toy evidence"], "validation": ["MCP-only E2E completed"], "next_action": "continue with a real experiment or stop toy validation", "artifact_refs": [str(evidence)]}))
    resume = _ok(call_tool("cs_resume_brief", {"project": str(project), "quest_id": quest_id, "max_chars": 5000}))
    next_action_after_resume = _ok(call_tool("cs_goal_next_action", {"project": str(project), "quest_id": quest_id}))

    return {
        "quest_id": quest_id,
        "idea": idea,
        "experiment": experiment,
        "action_after_experiment": action_after_experiment,
        "scoreboard": scoreboard,
        "selected": selected,
        "claim": claim,
        "checkpoint": checkpoint,
        "resume": resume,
        "next_action_after_resume": next_action_after_resume,
        "evidence": evidence,
    }


def test_goal_e2e_toy_research_runs_complete_mcp_only_flow(tmp_path: Path):
    result = run_toy_goal_research(tmp_path)
    quest_id = result["quest_id"]

    assert result["experiment"]["method_improvement_due"] is True
    assert result["action_after_experiment"]["next_action"]["required_tool"] == "cs_update_method_scoreboard"
    assert result["scoreboard"]["scoreboard"]["ideas"]["toy-normalize"]["outcome"] == "positive"
    assert result["selected"]["next_idea"]["idea_id"] == "toy-normalize"
    assert result["claim"]["claim_gate"]["claimable"] is True
    assert result["checkpoint"]["checkpoint_id"]
    assert result["resume"]["current_quest"] == quest_id
    assert result["resume"]["last_completed_action"] == "claim-gate"
    assert result["evidence"].exists()

    quest_root = tmp_path / "CodexScientist" / "quests" / quest_id
    assert quest_root.exists()
    assert (quest_root / "method_memory" / "scoreboard" / "scoreboard.json").exists()
    assert (quest_root / "artifacts" / "decisions" / "claim_gate_toy-claim.json").exists()

    repo_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in tmp_path.rglob("*.json") if path.is_file())
    for forbidden in FORBIDDEN:
        assert forbidden not in repo_text


def test_p4_acceptance_includes_final_goal_e2e_tests():
    source = (ROOT / "scripts" / "p4_acceptance.py").read_text(encoding="utf-8")
    assert "tests/test_goal_e2e_toy_research.py" in source
    assert "tests/test_goal_e2e_no_cli_invocation.py" in source
    assert "tests/test_goal_e2e_resume_after_compaction.py" in source
