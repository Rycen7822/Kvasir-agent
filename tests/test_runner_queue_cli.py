from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_csctl(*args: str, project_root: Path) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "csctl.py"), "--project-root", str(project_root), *args],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_runner_and_queue_cli_expose_minimal_stable_control_surface(tmp_path: Path):
    started = run_csctl("runner", "start", "--command", "python train.py", "--dry-run", "--format", "json", project_root=tmp_path)
    assert started["run"]["run_id"] == "R0001"
    assert started["run"]["status"] == "dry_run"

    collected = run_csctl("runner", "collect", "R0001", "--exit-code", "1", "--format", "json", project_root=tmp_path)
    assert collected["run"]["status"] == "failed_other"
    assert collected["run"]["terminal"] is True

    submitted = run_csctl("queue", "submit", "--job-id", "job1", "--command", "python train.py", "--format", "json", project_root=tmp_path)
    assert submitted["job"]["status"] == "pending"

    updated = run_csctl("queue", "update", "job1", "--status", "completed", "--format", "json", project_root=tmp_path)
    assert updated["job"]["terminal"] is True

    status = run_csctl("queue", "status", "--format", "json", project_root=tmp_path)
    assert status["all_done"] is True
    assert status["jobs"]["job1"]["status"] == "completed"
