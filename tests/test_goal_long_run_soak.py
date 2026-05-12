from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, json.dumps(payload, ensure_ascii=False, indent=2)
    return payload


def _confirm_baseline(tmp_path: Path, quest_id: str) -> None:
    baseline = _ok(
        call_tool(
            "cs_create_local_baseline",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "baseline_id": "toy_baseline",
                "summary": "Toy baseline.",
                "overwrite": True,
            },
        )
    )
    _ok(call_tool("cs_confirm_baseline", {"project": str(tmp_path), **baseline["confirm_args"]}))


def test_goal_long_run_soak_reaches_checkpoint_without_cli_surface(tmp_path: Path):
    quest = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "toy long run", "title": "Toy Long Run"}))
    quest_id = quest["quest"]["quest_id"]
    _ok(call_tool("cs_record_user_requirement", {"project": str(tmp_path), "quest_id": quest_id, "message": "toy only"}))
    _confirm_baseline(tmp_path, quest_id)
    _ok(
        call_tool(
            "cs_submit_idea",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "title": "Toy idea",
                "mechanism": "toy mechanism",
                "hypothesis": "toy",
                "novelty_contract": {
                    "mechanism": "toy mechanism",
                    "related_work_refs": ["toy-baseline"],
                    "expected_difference": "bounded toy route",
                    "risk_notes": ["toy-only"],
                },
            },
        )
    )
    _ok(call_tool("cs_runner_start", {"project": str(tmp_path), "quest_id": quest_id, "command": "python train.py", "dry_run": True}))
    _ok(
        call_tool(
            "cs_record_main_experiment",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "run_id": "toy-run-soak",
                "title": "Toy run",
                "hypothesis": "toy",
                "metric_rows": [{"metric": "primary", "value": 1.0}],
                "metrics_summary": {"primary": 1.0},
                "evidence_paths": [],
                "verdict": "candidate",
            },
        )
    )
    _ok(call_tool("cs_update_method_scoreboard", {"project": str(tmp_path), "quest_id": quest_id, "idea_id": "toy", "outcome": "positive", "metric_delta": 0.1, "mechanism": "toy mechanism"}))
    checkpoint = _ok(call_tool("cs_checkpoint", {"project": str(tmp_path), "quest_id": quest_id, "phase": "soak", "completed": ["toy-loop"], "next_action": "analysis"}))
    resume = _ok(call_tool("cs_resume_brief", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 5000}))

    assert checkpoint["checkpoint_id"]
    assert resume["current_quest"] == quest_id
    assert resume["next_required_mcp_tool"]
    repo_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in tmp_path.rglob("*.json") if path.is_file())
    assert "scripts/csctl.py" not in repo_text
    assert "CLI fallback" not in repo_text
