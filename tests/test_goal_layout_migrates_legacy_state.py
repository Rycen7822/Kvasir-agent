from __future__ import annotations

import json
from pathlib import Path

from kvasir_agent.services.project_state import ProjectLayout
from kvasir_agent.services.queue import QueueService
from kvasir_agent.services.runner import RunnerService
from kvasir_agent.services.trial import TrialService


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_queue_runner_trial_new_writes_use_root_bound_paths(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    quest_id = "Q-001"

    queue = QueueService(layout)
    submitted = queue.submit(job_id="job1", command="python train.py", quest_id=quest_id)
    job = submitted["job"]
    assert job["quest_id"] == quest_id
    assert Path(job["quest_root"]) == layout.state_root
    assert "detail_path" not in job
    assert _load(layout.state_root / "queue" / "queue_state.json")["jobs"]["job1"]["quest_root"] == str(layout.state_root)

    runner = RunnerService(layout)
    started = runner.start(command="python train.py", job_id="job1", dry_run=True, quest_id=quest_id)
    run = started["run"]
    assert run["quest_id"] == quest_id
    assert Path(run["quest_root"]) == layout.state_root
    assert "detail_path" not in run
    assert _load(layout.state_root / "runs" / run["run_id"] / "runner.json")["quest_root"] == str(layout.state_root)

    trial = TrialService(layout).propose(
        quest_id=quest_id,
        idea_id="I1",
        hypothesis="toy hypothesis",
        mechanism="toy mechanism",
    )
    assert trial["quest_id"] == quest_id
    assert Path(trial["quest_root"]) == layout.state_root
    assert "detail_path" not in trial
    assert _load(layout.state_root / "trials" / trial["trial_id"] / "trial.json")["quest_root"] == str(layout.state_root)
    assert not (layout.state_root / "quests" / quest_id).exists()
