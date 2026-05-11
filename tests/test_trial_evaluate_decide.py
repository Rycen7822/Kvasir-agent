from __future__ import annotations

from pathlib import Path


def _ready_trial(tmp_path: Path):
    from codex_scientist.services.manifest import ManifestService
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.trial import TrialService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest_service = ManifestService(layout)
    manifest = manifest_service.default_manifest(name="Demo", goal="Improve")
    manifest["metrics"]["primary"]["validation"]["required_artifacts"] = ["metrics.json"]
    manifest["baselines"]["entries"].append({"id": "b1", "status": "confirmed", "metric_contract": "primary", "artifact_requirements": []})
    manifest_service.write(manifest)
    trial_service = TrialService(layout)
    trial = trial_service.propose(quest_id="q1", idea_id="i1", hypothesis="h", mechanism="m")
    trial_service.plan(trial["trial_id"], metric_contract_id="primary", novelty_decision="allow")
    trial_service.ready(trial["trial_id"])
    return trial_service, trial["trial_id"]


def test_trial_evaluate_missing_required_artifact_fails_and_cannot_keep(tmp_path: Path):
    trial_service, trial_id = _ready_trial(tmp_path)

    evaluated = trial_service.evaluate(trial_id, metric_values={"primary": 0.9}, artifacts=[])
    assert evaluated["ok"] is False
    assert evaluated["error_type"] == "failed_artifact"
    assert evaluated["trial"]["status"] == "failed_artifact"

    decision = trial_service.decide(trial_id, decision="keep", reviewer_verdict="pass")
    assert decision["ok"] is False
    assert decision["error_type"] == "cannot_keep_failed_trial"


def test_trial_evaluate_with_metric_and_artifact_can_be_kept_after_review_pass(tmp_path: Path):
    trial_service, trial_id = _ready_trial(tmp_path)

    evaluated = trial_service.evaluate(trial_id, metric_values={"primary": 0.9}, artifacts=["metrics.json"])
    assert evaluated["ok"] is True
    assert evaluated["trial"]["status"] == "evaluated"

    decision = trial_service.decide(trial_id, decision="keep", reviewer_verdict="pass")
    assert decision["ok"] is True
    assert decision["trial"]["status"] == "kept"
