from __future__ import annotations

from pathlib import Path


def test_trial_fsm_rejects_invalid_transition_and_blocks_ready_without_baseline(tmp_path: Path):
    from codex_scientist.services.manifest import ManifestService
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.trial import TrialService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest_service = ManifestService(layout)
    manifest_service.write(manifest_service.default_manifest(name="Demo", goal="Improve result"))

    trial_service = TrialService(layout)
    trial = trial_service.propose(quest_id="q1", idea_id="i1", hypothesis="h", mechanism="m")
    assert trial["status"] == "proposed"

    invalid = trial_service.transition(trial["trial_id"], "running")
    assert invalid["ok"] is False
    assert invalid["error_type"] == "invalid_transition"

    planned = trial_service.plan(trial["trial_id"], metric_contract_id="primary", novelty_decision="allow")
    assert planned["ok"] is True
    assert planned["trial"]["status"] == "planned"

    blocked = trial_service.ready(trial["trial_id"])
    assert blocked["ok"] is False
    assert blocked["error_type"] == "baseline_required"
    assert blocked["trial"]["status"] == "planned"


def test_trial_ready_succeeds_after_confirmed_baseline(tmp_path: Path):
    from codex_scientist.services.manifest import ManifestService
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.trial import TrialService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest_service = ManifestService(layout)
    manifest = manifest_service.default_manifest(name="Demo", goal="Improve result")
    manifest["baselines"]["entries"].append({"id": "b1", "status": "confirmed", "metric_contract": "primary", "artifact_requirements": []})
    manifest_service.write(manifest)

    trial_service = TrialService(layout)
    trial = trial_service.propose(quest_id="q1", idea_id="i1", hypothesis="h", mechanism="m")
    trial_service.plan(trial["trial_id"], metric_contract_id="primary", novelty_decision="allow")

    ready = trial_service.ready(trial["trial_id"])
    assert ready["ok"] is True
    assert ready["trial"]["status"] == "ready"
