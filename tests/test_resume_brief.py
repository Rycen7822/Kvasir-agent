from __future__ import annotations

from pathlib import Path

from codex_scientist.services.checkpoint import CheckpointService
from codex_scientist.services.manifest import ManifestService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.resume import ResumeService

_REQUIRED_RESUME_KEYS = {
    "goal",
    "autonomy_mode",
    "active_phase",
    "active_trial_id",
    "active_job_id",
    "active_run_id",
    "last_checkpoint",
    "recovery_anchor",
    "blocked_reason",
    "validation_status",
    "budget_status",
    "artifact_refs",
    "risk_flags",
    "source_refs",
}


def test_resume_brief_contains_stable_recovery_anchors(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    ManifestService(layout).init(name="demo", goal="make context recovery stable")
    checkpoint = CheckpointService(layout).create_checkpoint(
        phase="P3-2",
        completed=["checkpoint service"],
        decisions=["use project-local compact state"],
        validation=["unit test"],
        next_action="implement delta pack",
        artifact_refs=[{"path": "CodexScientist/summaries/latest_checkpoint.json"}],
        risk_flags=["budget_too_small_if_under_anchor_floor"],
    )

    brief = ResumeService(layout).resume_brief(max_chars=8000, include_recent_events=3, include_risks=True)

    assert brief["ok"] is True
    assert _REQUIRED_RESUME_KEYS <= set(brief)
    assert brief["goal"]["title"] == "make context recovery stable"
    assert brief["autonomy_mode"] == "copilot"
    assert brief["active_phase"] == "P3-2"
    assert brief["last_checkpoint"]["checkpoint_id"] == checkpoint["checkpoint_id"]
    assert brief["recovery_anchor"] == "implement delta pack"
    assert brief["artifact_refs"]
    assert brief["source_refs"]


def test_resume_brief_warns_instead_of_dropping_anchors_when_budget_is_too_small(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    ManifestService(layout).init(name="demo", goal="preserve anchors")

    brief = ResumeService(layout).resume_brief(max_chars=120, include_recent_events=1, include_risks=True)

    assert brief["ok"] is True
    assert _REQUIRED_RESUME_KEYS <= set(brief)
    assert "budget_too_small" in brief["warnings"]
    assert brief["recovery_anchor"]
