from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

QUEST_ID = "QWORKER"
ENV_ID = "env_worker"
VARIANT_ID = "var_worker"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup(tmp_path: Path) -> tuple[ProjectLayout, str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "train.py").write_text("print('train')\n", encoding="utf-8")
    (repo / "eval.py").write_text("print('eval')\n", encoding="utf-8")
    (repo / "data.jsonl").write_text("{}\n", encoding="utf-8")
    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = {
        "schema_version": 1,
        "env_id": ENV_ID,
        "quest_id": QUEST_ID,
        "title": "Worker env",
        "problem": "run toy local job",
        "baseline": {"repo_path": "repo", "baseline_metric": {"name": "score", "value": 0.5, "direction": "maximize"}},
        "mutable_allowlist": ["repo/train.py"],
        "protected_files": [{"path": "repo/eval.py", "sha256": _sha256(repo / "eval.py")}],
        "datasets": [{"path": "repo/data.jsonl", "sha256": _sha256(repo / "data.jsonl")}],
        "commands": {"setup": [["python", "-V"]], "smoke": [["python", "-V"]], "run": [["python", "-V"]], "evaluate": [["python", "-V"]]},
        "primary_metric": {"name": "score", "direction": "maximize", "parser": "json_path", "path": "metrics.score"},
        "sample_metrics": {"metrics": {"score": 0.5}},
        "resources": {"gpu_count": 0},
        "budget": {"max_gpu_hours": 0.0, "max_usd": 0.0},
        "security": {"network_policy": "restricted"},
    }
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True
    created = TrajectoryStore(layout).create(quest_id=QUEST_ID, env_id=ENV_ID, idea={"idea_id": "idea_worker", "title": "worker idea"})
    assert created["ok"] is True, created
    trajectory_id = created["trajectory_id"]
    archive = tmp_path / "package.tar.gz"
    archive.write_bytes(b"toy-package")
    package = tmp_path / "package.json"
    package.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "quest_id": QUEST_ID,
                "env_id": ENV_ID,
                "variant_id": VARIANT_ID,
                "trajectory_id": trajectory_id,
                "archive_path": str(archive),
                "archive_sha256": _sha256(archive),
                "protected_hash_report": EnvironmentService(layout).protected_hash_report(quest_id=QUEST_ID, env_id=ENV_ID),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return layout, trajectory_id, package


def test_worker_claim_runs_collects_feedback_and_updates_trajectory(tmp_path: Path):
    from codex_scientist.services.scheduler import SchedulerService
    from codex_scientist.services.worker import WorkerService

    layout, trajectory_id, package = _setup(tmp_path)
    command = f"{sys.executable} -c \"import json; json.dump({{'metrics': {{'score': 0.82}}}}, open('metrics.json','w'))\""
    submitted = SchedulerService(layout).submit(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        variant_id=VARIANT_ID,
        package_path=str(package),
        backend="local",
        command=command,
        expected_outputs=["metrics.json"],
    )
    assert submitted["ok"] is True, submitted

    claimed = WorkerService(layout).claim(worker_id="worker-1")
    assert claimed["ok"] is True, claimed
    assert claimed["job"]["status"] == "running"
    run_id = claimed["run"]["run_id"]

    collected: dict = {"ok": False}
    for _ in range(30):
        collected = WorkerService(layout).collect(job_id=submitted["job"]["job_id"], trusted_primary_metric=True)
        if collected.get("collected") is True and collected.get("job", {}).get("terminal") is True:
            break
        time.sleep(0.05)

    assert collected["ok"] is True, collected
    assert collected["run"]["run_id"] == run_id
    assert collected["job"]["status"] == "completed"
    assert collected["feedback"]["primary_metric"]["value"] == 0.82
    shown = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)
    assert shown["trajectory"]["result"]["status"] == "evaluated"
    assert shown["trajectory"]["result"]["primary_metric"]["value"] == 0.82


def test_worker_collect_invalid_metrics_fails_job_and_does_not_mark_claimable(tmp_path: Path):
    from codex_scientist.services.scheduler import SchedulerService
    from codex_scientist.services.worker import WorkerService

    layout, trajectory_id, package = _setup(tmp_path)
    command = f"{sys.executable} -c \"import json; json.dump({{'metrics': {{'other': 0.82}}}}, open('metrics.json','w'))\""
    submitted = SchedulerService(layout).submit(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        variant_id=VARIANT_ID,
        package_path=str(package),
        backend="local",
        command=command,
        expected_outputs=["metrics.json"],
    )
    assert submitted["ok"] is True, submitted
    assert WorkerService(layout).claim(worker_id="worker-1")["ok"] is True

    collected: dict = {"ok": False}
    for _ in range(30):
        collected = WorkerService(layout).collect(job_id=submitted["job"]["job_id"], trusted_primary_metric=True)
        if collected.get("collected") is True and collected.get("job", {}).get("terminal") is True:
            break
        time.sleep(0.05)

    assert collected["ok"] is False, collected
    assert collected["error_type"] in {"metric_missing", "metric_invalid"}
    assert collected["job"]["status"] == "failed_metric"
    shown = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)
    assert shown["trajectory"]["result"]["trusted_primary_metric"] is False
    assert shown["trajectory"]["claimability"]["claim_gate_status"] == "needs_revalidation"


def test_worker_collect_missing_metrics_maps_to_metric_missing(tmp_path: Path):
    from codex_scientist.services.scheduler import SchedulerService
    from codex_scientist.services.worker import WorkerService

    layout, trajectory_id, package = _setup(tmp_path)
    submitted = SchedulerService(layout).submit(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        variant_id=VARIANT_ID,
        package_path=str(package),
        backend="local",
        command=f"{sys.executable} -c \"print('no metrics')\"",
        expected_outputs=["metrics.json"],
    )
    assert submitted["ok"] is True, submitted
    assert WorkerService(layout).claim(worker_id="worker-1")["ok"] is True

    collected: dict = {"ok": False}
    for _ in range(30):
        collected = WorkerService(layout).collect(job_id=submitted["job"]["job_id"], trusted_primary_metric=True)
        if collected.get("collected") is True and collected.get("job", {}).get("terminal") is True:
            break
        time.sleep(0.05)

    assert collected["ok"] is False
    assert collected["error_type"] == "metric_missing"
    shown = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)
    assert shown["trajectory"]["failure"]["class"] == "metric_missing"
