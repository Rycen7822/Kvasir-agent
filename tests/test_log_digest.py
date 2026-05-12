from __future__ import annotations

from pathlib import Path

from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.runner import RunnerService


def test_runner_log_digest_returns_bounded_redacted_log_reference(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    started = RunnerService(layout).start(command="python train.py", dry_run=True)
    run = started["run"]
    log_path = Path(run["log_path"])
    log_path.write_text(
        "\n".join([
            "epoch 1 ok",
            "token=" + "supersecret",
            "Traceback (most recent call last):",
            "RuntimeError: CUDA out of memory password=" + "hunter2",
        ]),
        encoding="utf-8",
    )

    digest = RunnerService(layout).log_digest(run["run_id"], max_tail_lines=3)

    assert digest["ok"] is True
    assert digest["run_id"] == run["run_id"]
    assert digest["status"] == "dry_run"
    assert digest["log_path"] == str(log_path)
    assert digest["bytes"] == log_path.stat().st_size
    assert len(digest["sha256"]) == 64
    assert digest["top_error_class"] == "oom"
    assert digest["suggested_next_action"]
    assert len(digest["last_semantic_events"]) <= 3
    rendered = str(digest)
    assert "supersecret" not in rendered
    assert "hunter2" not in rendered
    assert "[REDACTED]" in rendered
