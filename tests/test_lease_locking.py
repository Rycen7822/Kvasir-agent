from __future__ import annotations


def test_queue_expired_lease_reconcile_marks_reconcile_required_not_pending(tmp_path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.queue import QueueService

    queue = QueueService(ProjectLayout.from_project_root(tmp_path))
    queue.submit(job_id="job1", command="python train.py")
    leased = queue.lease_next(worker_id="w1", ttl_seconds=0)
    assert leased["job"]["status"] == "leased"

    reconciled = queue.reconcile_expired_leases()
    assert reconciled["jobs"]["job1"]["status"] == "reconcile_required"
    assert reconciled["jobs"]["job1"]["terminal"] is False
    assert reconciled["jobs"]["job1"]["retryable"] is False
