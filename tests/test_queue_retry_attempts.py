from __future__ import annotations

import sys

from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.queue import QueueService
from codex_scientist.services.runner import RunnerService


def test_queue_attempt_retry_starts_new_run_id_per_retry(tmp_path):
    layout = ProjectLayout.from_project_root(tmp_path)
    queue = QueueService(layout)
    runner = RunnerService(layout)
    queue.submit(job_id="job1", command=f"{sys.executable} -c \"print('attempt')\"", max_attempts=2, retry_policy="oom_or_transient", resource={"gpu": 1})

    first = queue.start_attempt("job1", runner=runner, worker_id="w1")
    runner.update_status(first["run"]["run_id"], "failed_oom", exit_code=137)
    queue.reconcile_expired_leases()
    retry = queue.start_attempt("job1", runner=runner, worker_id="w1")

    job = retry["job"]
    assert first["run"]["run_id"] == "R0001"
    assert retry["run"]["run_id"] == "R0002"
    assert job["attempts"] == 2
    assert job["run_ids"] == ["R0001", "R0002"]
    assert job["status"] == "running"
    assert job["max_attempts"] == 2
    assert job["retry_policy"] == "oom_or_transient"
    assert job["resource"] == {"gpu": 1}

    runner.update_status(retry["run"]["run_id"], "failed_oom", exit_code=137)
    queue.reconcile_expired_leases()
    capped = queue.start_attempt("job1", runner=runner, worker_id="w1")
    assert capped["ok"] is False
    assert capped["error_type"] == "max_attempts_exceeded"


def test_queue_running_job_does_not_start_duplicate_attempt(tmp_path):
    layout = ProjectLayout.from_project_root(tmp_path)
    queue = QueueService(layout)
    runner = RunnerService(layout)
    queue.submit(job_id="job1", command=f"{sys.executable} -c \"print('attempt')\"")
    first = queue.start_attempt("job1", runner=runner, worker_id="w1")

    duplicate = queue.start_attempt("job1", runner=runner, worker_id="w1")

    assert first["ok"] is True
    assert duplicate["ok"] is False
    assert duplicate["error_type"] == "not_attemptable"
    assert [run["run_id"] for run in runner.list_runs()] == ["R0001"]
