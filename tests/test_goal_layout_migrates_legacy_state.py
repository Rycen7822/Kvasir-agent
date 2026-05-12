from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.queue import QueueService
from codex_scientist.services.runner import RunnerService
from codex_scientist.services.trial import TrialService


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_queue_runner_trial_new_writes_include_quest_detail_paths(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    quest_id = "Q-001"
    layout.ensure_quest_layout(quest_id)

    queue = QueueService(layout)
    submitted = queue.submit(job_id="job1", command="python train.py", quest_id=quest_id)
    job = submitted["job"]
    assert job["quest_id"] == quest_id
    assert Path(job["quest_root"]) == layout.quest_root_for(quest_id)
    assert Path(job["detail_path"]) == layout.quest_detail_path(quest_id, "runtime/queue/job1.json")
    assert _load(job["detail_path"])["job_id"] == "job1"
    assert _load(layout.state_root / "queue" / "queue_state.json")["jobs"]["job1"]["detail_path"] == job["detail_path"]

    runner = RunnerService(layout)
    started = runner.start(command="python train.py", job_id="job1", dry_run=True, quest_id=quest_id)
    run = started["run"]
    assert run["quest_id"] == quest_id
    assert Path(run["quest_root"]) == layout.quest_root_for(quest_id)
    assert Path(run["detail_path"]) == layout.quest_detail_path(quest_id, f"runtime/runs/{run['run_id']}/runner.json")
    assert _load(run["detail_path"])["run_id"] == run["run_id"]
    assert _load(layout.state_root / "runs" / run["run_id"] / "runner.json")["detail_path"] == run["detail_path"]

    trial = TrialService(layout).propose(
        quest_id=quest_id,
        idea_id="I1",
        hypothesis="toy hypothesis",
        mechanism="toy mechanism",
    )
    assert trial["quest_id"] == quest_id
    assert Path(trial["quest_root"]) == layout.quest_root_for(quest_id)
    assert Path(trial["detail_path"]) == layout.quest_detail_path(quest_id, f"experiments/trials/{trial['trial_id']}/trial.json")
    assert _load(trial["detail_path"])["trial_id"] == trial["trial_id"]
    assert _load(layout.state_root / "trials" / trial["trial_id"] / "trial.json")["detail_path"] == trial["detail_path"]


def test_mcp_bridge_passes_quest_id_into_project_local_details(tmp_path: Path):
    quest_id = "Q-002"
    layout = ProjectLayout.from_project_root(tmp_path)
    layout.ensure_quest_layout(quest_id)

    queue = call_tool("cs_queue_submit", {"project": str(tmp_path), "quest_id": quest_id, "job_id": "job2", "command": "python train.py"})
    assert queue["ok"] is True
    assert queue["job"]["quest_id"] == quest_id
    assert Path(queue["job"]["detail_path"]).exists()

    run = call_tool("cs_runner_start", {"project": str(tmp_path), "quest_id": quest_id, "job_id": "job2", "command": "python train.py", "dry_run": True})
    assert run["ok"] is True
    assert run["run"]["quest_id"] == quest_id
    assert Path(run["run"]["detail_path"]).exists()

    trial = call_tool(
        "cs_trial_propose",
        {"project": str(tmp_path), "quest_id": quest_id, "idea_id": "I2", "hypothesis": "h", "mechanism": "m"},
    )
    assert trial["ok"] is True
    assert trial["trial"]["quest_id"] == quest_id
    assert Path(trial["trial"]["detail_path"]).exists()
