from __future__ import annotations

from pathlib import Path


def test_runner_start_is_nonblocking_and_collect_failed_other_is_terminal(tmp_path: Path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.runner import RunnerService

    runner = RunnerService(ProjectLayout.from_project_root(tmp_path))
    started = runner.start(command="python train.py", job_id="job1", dry_run=True)

    assert started["ok"] is True
    assert started["run"]["run_id"] == "R0001"
    assert started["run"]["status"] == "dry_run"
    assert Path(started["run"]["log_path"]).is_relative_to(tmp_path / "CodexScientist")

    collected = runner.collect("R0001", exit_code=1)
    assert collected["ok"] is True
    assert collected["run"]["status"] == "failed_other"
    assert collected["run"]["terminal"] is True


def test_runner_tail_limits_and_redacts_secret_like_content(tmp_path: Path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.runner import RunnerService

    runner = RunnerService(ProjectLayout.from_project_root(tmp_path))
    started = runner.start(command="python train.py", dry_run=True)
    log_path = Path(started["run"]["log_path"])
    log_path.write_text("line1\ntoken=abc123\nline3\n", encoding="utf-8")

    tail = runner.tail("R0001", limit=2)
    assert tail["ok"] is True
    assert tail["lines"] == ["token=[REDACTED]", "line3"]
    assert "abc123" not in "\n".join(tail["lines"])
