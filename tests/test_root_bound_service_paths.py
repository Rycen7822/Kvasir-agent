from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.feedback_ingest import FeedbackIngestService
from codex_scientist.services.goal_loop import GoalLoopService
from codex_scientist.services.journal import JournalService
from codex_scientist.services.method_improvement import MethodImprovementService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.queue import QueueService
from codex_scientist.services.runner import RunnerService
from codex_scientist.services.trajectory import TrajectoryStore
from codex_scientist.services.trial import TrialService


QUEST_ID = "QROOT"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _env_manifest(project: Path, *, quest_id: str = QUEST_ID, env_id: str = "env_root") -> dict:
    baseline = project / "baseline.txt"
    dataset = project / "dataset.txt"
    baseline.write_text("baseline\n", encoding="utf-8")
    dataset.write_text("dataset\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "env_id": env_id,
        "quest_id": quest_id,
        "title": "root-bound env",
        "problem": "root-bound service path test",
        "baseline": {"repo_path": ".", "baseline_metric": {"value": 0.5, "direction": "maximize"}},
        "mutable_allowlist": ["results"],
        "protected_files": [{"path": "baseline.txt", "sha256": _sha256(baseline)}],
        "datasets": [{"path": "dataset.txt", "sha256": _sha256(dataset)}],
        "commands": {name: [["python", "-c", "print('ok')"]] for name in ("setup", "smoke", "run", "evaluate")},
        "primary_metric": {"name": "score", "direction": "maximize", "parser": "flat_key", "key": "score"},
        "sample_metrics": {"score": 0.6},
        "resources": {},
        "budget": {},
        "security": {},
    }


def test_core_services_write_root_bound_paths_without_quest_detail_copy(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)

    env = EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=_env_manifest(tmp_path))
    assert env["ok"] is True, env
    assert Path(env["path"]) == tmp_path / "CodexScientist" / "environments" / "env_root.json"

    negative = JournalService(layout).record_negative_result(trial_id="TNEG", idea_id="I1", failure_reason="regressed", lesson="avoid duplicate", quest_id=QUEST_ID)
    assert Path(negative["negative_memory_path"]) == tmp_path / "CodexScientist" / "method_memory" / "negative" / "negative_memory.jsonl"

    method = MethodImprovementService(layout).update_scoreboard(quest_id=QUEST_ID, idea_id="I1", outcome="positive", metric_delta=0.1)
    assert Path(method["scoreboard_path"]) == tmp_path / "CodexScientist" / "method_memory" / "scoreboard" / "scoreboard.json"
    assert MethodImprovementService(layout).frontier_path(QUEST_ID) == tmp_path / "CodexScientist" / "method_memory" / "frontier" / "frontier.json"

    trial = TrialService(layout).propose(quest_id=QUEST_ID, idea_id="I1", hypothesis="h", mechanism="m")
    assert trial["quest_root"] == str(tmp_path / "CodexScientist")
    assert "detail_path" not in trial
    assert (tmp_path / "CodexScientist" / "trials" / trial["trial_id"] / "trial.json").exists()

    goal = GoalLoopService(layout).write_state(QUEST_ID, active_stage="experiment")
    assert Path(goal["path"]) == tmp_path / "CodexScientist" / "runtime" / "goal_state.json"
    assert goal["state"]["quest_root"] == str(tmp_path / "CodexScientist")
    assert "quest_id" not in goal["state"]["next_action"].get("required_inputs", [])

    queued = QueueService(layout).submit(job_id="job1", command="echo ok", quest_id=QUEST_ID)
    job = queued["job"]
    assert job["quest_root"] == str(tmp_path / "CodexScientist")
    assert "detail_path" not in job
    assert (tmp_path / "CodexScientist" / "queue" / "queue_state.json").exists()

    run = RunnerService(layout).start(command="echo ok", dry_run=True, quest_id=QUEST_ID)["run"]
    assert run["quest_root"] == str(tmp_path / "CodexScientist")
    assert "detail_path" not in run
    assert Path(run["log_path"]).is_relative_to(tmp_path / "CodexScientist" / "runs")

    assert not (tmp_path / "CodexScientist" / "quests").exists()


def test_execution_grounded_feedback_uses_root_bound_artifact_dir(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=_env_manifest(tmp_path))["ok"] is True
    created = TrajectoryStore(layout).create(quest_id=QUEST_ID, env_id="env_root", idea={"idea_id": "idea1"})
    assert created["ok"] is True, created
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"score": 0.75}), encoding="utf-8")

    feedback = FeedbackIngestService(layout).ingest(
        quest_id=QUEST_ID,
        env_id="env_root",
        trajectory_id=created["trajectory_id"],
        run_id="RROOT",
        source_kind="local_metrics",
        metrics_path=str(metrics),
        trusted_primary_metric=True,
    )

    assert feedback["ok"] is True, feedback
    assert Path(feedback["path"]) == tmp_path / "CodexScientist" / "artifacts" / "execution_grounded" / "RROOT" / "feedback_bundle.json"
    assert not (tmp_path / "CodexScientist" / "quests").exists()


def test_service_layer_has_no_non_legacy_quest_detail_path_calls():
    services_dir = Path(__file__).parents[1] / "codex_scientist" / "services"
    forbidden = [
        "ensure_quest_layout(",
        "quest_root_for(",
        "quest_detail_path(",
        "quest_run_dir(",
        "quest_trial_path(",
    ]
    offenders: list[str] = []
    for path in services_dir.glob("*.py"):
        if path.name == "project_state.py":
            continue
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in source:
                offenders.append(f"{path.name}:{token}")
    assert offenders == []
