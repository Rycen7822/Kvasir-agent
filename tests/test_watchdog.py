from __future__ import annotations


def test_watchdog_marks_stale_running_run_as_stuck(tmp_path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.runner import RunnerService
    from codex_scientist.services.watchdog import WatchdogService

    layout = ProjectLayout.from_project_root(tmp_path)
    runner = RunnerService(layout)
    runner.start(command="python train.py", dry_run=False)

    watchdog = WatchdogService(layout)
    result = watchdog.reconcile_stale_runs(timeout_seconds=0)

    assert result["ok"] is True
    assert result["stuck_runs"] == ["R0001"]
    assert runner.get("R0001")["status"] == "stuck"
