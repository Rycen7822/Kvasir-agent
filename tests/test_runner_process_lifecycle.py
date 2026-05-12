from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.runner import RunnerService


def test_runner_real_subprocess_collects_log_pid_and_heartbeat(tmp_path: Path):
    runner = RunnerService(ProjectLayout.from_project_root(tmp_path))
    command = f"{sys.executable} -c \"print('done', flush=True)\""

    started = runner.start(command=command, dry_run=False)
    run = started["run"]
    assert run["status"] == "running"
    assert run["pid"] > 0
    assert run["pgid"] > 0
    assert Path(run["heartbeat_path"]).exists()

    deadline = time.time() + 5
    while time.time() < deadline and runner.is_process_alive(run["pid"]):
        time.sleep(0.05)
    collected = runner.collect(run["run_id"])

    assert collected["run"]["status"] == "completed"
    assert collected["run"]["exit_code"] == 0
    digest = runner.log_digest(run["run_id"])
    assert digest["ok"] is True
    assert digest["top_error_class"] == "none"
    assert isinstance(digest["heartbeat_age_seconds"], (int, float))
    assert digest["stderr_log_path"].endswith("stderr.log")
    assert digest["last_stderr_digest"] == []
    assert "done" in "\n".join(digest["last_semantic_events"])


def test_runner_log_digest_includes_stderr_digest_and_error_class(tmp_path: Path):
    runner = RunnerService(ProjectLayout.from_project_root(tmp_path))
    command = f"{sys.executable} -c \"import sys; print('stdout ok'); print('Traceback: boom', file=sys.stderr)\""
    started = runner.start(command=command, dry_run=False)
    run = started["run"]
    deadline = time.time() + 5
    while time.time() < deadline and runner.is_process_alive(run["pid"]):
        time.sleep(0.05)
    runner.collect(run["run_id"])

    digest = runner.log_digest(run["run_id"])

    assert digest["top_error_class"] == "exception"
    assert "Traceback: boom" in "\n".join(digest["last_stderr_digest"])


def test_runner_collect_across_process_uses_exit_code_sentinel(tmp_path: Path):
    start_code = """
import sys
from pathlib import Path
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.runner import RunnerService
root = Path(sys.argv[1])
runner = RunnerService(ProjectLayout.from_project_root(root))
started = runner.start(command=f'{sys.executable} -c "import sys; sys.exit(7)"', dry_run=False)
print(started['run']['run_id'])
"""
    run_id = subprocess.check_output([sys.executable, "-c", start_code, str(tmp_path)], text=True).strip()
    time.sleep(0.4)
    collect_code = """
import json
import sys
from pathlib import Path
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.runner import RunnerService
root = Path(sys.argv[1])
run_id = sys.argv[2]
print(json.dumps(RunnerService(ProjectLayout.from_project_root(root)).collect(run_id)))
"""
    collected = json.loads(subprocess.check_output([sys.executable, "-c", collect_code, str(tmp_path), run_id], text=True))

    assert collected["run"]["status"] == "failed_other"
    assert collected["run"]["exit_code"] == 7


def test_runner_cancel_terminates_process_group_and_marks_terminal(tmp_path: Path):
    runner = RunnerService(ProjectLayout.from_project_root(tmp_path))
    command = f"{sys.executable} -c \"import time; print('ready', flush=True); time.sleep(30)\""
    started = runner.start(command=command, dry_run=False)
    run = started["run"]

    cancelled = runner.cancel(run["run_id"])

    assert cancelled["ok"] is True
    assert cancelled["run"]["status"] == "cancelled"
    assert cancelled["run"]["terminal"] is True
    assert runner.is_process_alive(run["pid"]) is False
