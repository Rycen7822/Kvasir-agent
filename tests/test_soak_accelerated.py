from __future__ import annotations

from pathlib import Path


def test_accelerated_soak_writes_validation_report_without_claiming_wall_clock_pass(tmp_path: Path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.soak import SoakService

    result = SoakService(ProjectLayout.from_project_root(tmp_path)).run_accelerated(days=10, inject_failures=True)

    assert result["ok"] is True
    assert result["accelerated"]["equivalent_days"] == 10
    assert result["accelerated"]["verdict"] == "pass"
    assert result["wall_clock"]["verdict"] == "not_run"
    report = Path(result["report_path"]).read_text(encoding="utf-8")
    assert "accelerated" in report
    assert "wall-clock: not_run" in report
    assert "do not claim stable ten-day wall-clock operation" in report


def test_crash_resume_reconciles_expired_lease_and_records_restart_event(tmp_path: Path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.queue import QueueService
    from codex_scientist.services.soak import SoakService

    layout = ProjectLayout.from_project_root(tmp_path)
    queue = QueueService(layout)
    queue.submit(job_id="job1", command="python train.py")
    queue.lease_next(worker_id="w1", ttl_seconds=0)

    result = SoakService(layout).crash_resume_smoke(restart_label="plugin-restart")

    assert result["ok"] is True
    assert result["queue"]["jobs"]["job1"]["status"] == "reconcile_required"
    assert result["restart_label"] == "plugin-restart"
