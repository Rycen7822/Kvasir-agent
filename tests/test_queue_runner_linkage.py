from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.queue import QueueService
from codex_scientist.services.runner import RunnerService


def test_queue_reconcile_links_runner_completion_and_expected_outputs(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    queue = QueueService(layout)
    runner = RunnerService(layout)
    artifact = layout.state_root / "artifacts" / "result.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("ok", encoding="utf-8")
    queue.submit(job_id="job1", command=f"{sys.executable} -c \"print('ok')\"")
    attempt = queue.start_attempt("job1", runner=runner, worker_id="w1", expected_outputs=[str(artifact)])
    runner.update_status(attempt["run"]["run_id"], "completed", exit_code=0)

    status = queue.reconcile_expired_leases()

    job = status["jobs"]["job1"]
    assert job["status"] == "completed"
    assert job["latest_run_id"] == "R0001"
    assert job["last_log_digest"]["run_id"] == "R0001"
    assert status["all_done"] is True
    assert status["all_done_reason"] == "all_jobs_terminal"


def test_queue_reconcile_across_process_does_not_mark_failed_run_completed(tmp_path: Path):
    start_code = """
import sys
from pathlib import Path
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.queue import QueueService
from codex_scientist.services.runner import RunnerService
root = Path(sys.argv[1])
layout = ProjectLayout.from_project_root(root)
queue = QueueService(layout)
runner = RunnerService(layout)
queue.submit(job_id='job1', command=f'{sys.executable} -c "import sys; sys.exit(7)"')
queue.start_attempt('job1', runner=runner, worker_id='w1')
"""
    subprocess.check_call([sys.executable, "-c", start_code, str(tmp_path)])
    reconcile_code = """
import json
import time
import sys
from pathlib import Path
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.queue import QueueService
root = Path(sys.argv[1])
time.sleep(0.4)
print(json.dumps(QueueService(ProjectLayout.from_project_root(root)).reconcile_expired_leases()))
"""
    status = json.loads(subprocess.check_output([sys.executable, "-c", reconcile_code, str(tmp_path)], text=True))

    job = status["jobs"]["job1"]
    assert job["status"] == "failed_other"
    assert job["last_log_digest"]["run_id"] == "R0001"
    assert status["all_done"] is True


def test_queue_reconcile_failed_artifact_when_expected_output_missing(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    queue = QueueService(layout)
    runner = RunnerService(layout)
    missing = layout.state_root / "artifacts" / "missing.txt"
    queue.submit(job_id="job1", command=f"{sys.executable} -c \"print('ok')\"")
    attempt = queue.start_attempt("job1", runner=runner, worker_id="w1", expected_outputs=[str(missing)])
    runner.update_status(attempt["run"]["run_id"], "completed", exit_code=0)

    status = queue.reconcile_expired_leases()

    job = status["jobs"]["job1"]
    assert job["status"] == "failed_artifact"
    assert job["stuck_taxonomy"] == "missing_expected_outputs"
    assert status["all_done"] is True
    assert status["all_done_reason"] == "all_jobs_terminal"


def test_queue_reconcile_missing_heartbeat_is_reconcile_required(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    queue = QueueService(layout)
    runner = RunnerService(layout)
    queue.submit(job_id="job1", command=f"{sys.executable} -c \"import time; time.sleep(30)\"")
    attempt = queue.start_attempt("job1", runner=runner, worker_id="w1")
    heartbeat = Path(attempt["run"]["heartbeat_path"])
    heartbeat.unlink()

    status = queue.reconcile_expired_leases()
    runner.cancel(attempt["run"]["run_id"])

    job = status["jobs"]["job1"]
    assert job["status"] == "reconcile_required"
    assert job["stuck_taxonomy"] == "missing_heartbeat"
    assert status["all_done"] is False
    assert status["all_done_reason"] == "active_jobs:job1"
