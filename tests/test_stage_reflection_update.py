from __future__ import annotations


def test_stage_reflection_outputs_plan_update_and_default_copilot_needs_user_decision(tmp_path):
    from codex_scientist.services.journal import JournalService
    from codex_scientist.services.manifest import ManifestService
    from codex_scientist.services.project_state import ProjectLayout

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = ManifestService(layout)
    manifest.write(manifest.default_manifest(name="Demo", goal="Improve"))

    journal = JournalService(layout)
    update = journal.record_stage_reflection(trigger="two_failures", gaps=["metric dropped"], next_sources=["review_gap", "paper_grounded"])

    assert update["plan_update"]["trigger"] == "two_failures"
    assert update["plan_update"]["status"] == "needs_user_decision"
    assert update["plan_update"]["created_running_trial"] is False


def test_novelty_check_blocks_duplicate_failed_idea(tmp_path):
    from codex_scientist.services.frontier import FrontierService
    from codex_scientist.services.journal import JournalService
    from codex_scientist.services.project_state import ProjectLayout

    layout = ProjectLayout.from_project_root(tmp_path)
    JournalService(layout).record_negative_result(trial_id="T0001", idea_id="I_old", failure_reason="duplicate mechanism", lesson="avoid widening layer blindly")

    decision = FrontierService(layout).check_novelty(idea_id="I_new", mechanism="avoid widening layer blindly")

    assert decision["decision"] == "block_duplicate"
    assert decision["similar_failed_ideas"] == ["I_old"]
