from __future__ import annotations


def test_queue_failed_other_is_terminal_and_snapshot_replays_from_events(tmp_path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.queue import QueueService

    queue = QueueService(ProjectLayout.from_project_root(tmp_path))
    queue.submit(job_id="job1", command="python a.py")
    queue.submit(job_id="job2", command="python b.py")
    queue.update_job("job1", "completed")
    queue.update_job("job2", "failed_other")

    status = queue.status()
    assert status["all_done"] is True
    assert status["jobs"]["job2"]["terminal"] is True
    assert status["jobs"]["job2"]["retryable"] is False

    queue.state_path.unlink()
    replayed = queue.status()
    assert replayed["all_done"] is True
    assert replayed["jobs"]["job1"]["status"] == "completed"
    assert replayed["jobs"]["job2"]["status"] == "failed_other"
