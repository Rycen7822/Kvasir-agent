from __future__ import annotations


def test_failed_trial_is_recorded_as_negative_memory(tmp_path):
    from codex_scientist.services.journal import JournalService
    from codex_scientist.services.project_state import ProjectLayout

    journal = JournalService(ProjectLayout.from_project_root(tmp_path))
    record = journal.record_negative_result(trial_id="T0001", idea_id="I1", failure_reason="metric dropped", lesson="Do not widen layer blindly")

    assert record["trial_id"] == "T0001"
    assert record["failure_reason"] == "metric dropped"
    assert journal.list_negative_memory() == [record]
