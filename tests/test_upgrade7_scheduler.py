from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

QUEST_ID = "QSCHED"
ENV_ID = "env_sched"
VARIANT_ID = "var_sched"


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
        "title": "Scheduler env",
        "problem": "submit toy local job",
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
    created = TrajectoryStore(layout).create(quest_id=QUEST_ID, env_id=ENV_ID, idea={"idea_id": "idea_sched", "title": "scheduler idea"})
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


def test_scheduler_local_submit_validates_package_and_creates_queue_job(tmp_path: Path):
    from codex_scientist.services.scheduler import SchedulerService

    layout, trajectory_id, package = _setup(tmp_path)
    command = f"{sys.executable} -c \"import json; json.dump({{'metrics': {{'score': 0.8}}}}, open('metrics.json','w'))\""

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
    assert submitted["job"]["status"] == "pending"
    assert submitted["job"]["resource"]["variant_id"] == VARIANT_ID
    assert submitted["job"]["expected_outputs"] == ["metrics.json"]


def test_scheduler_blocks_nonlocal_backend_and_protected_hash_mismatch(tmp_path: Path):
    from codex_scientist.services.scheduler import SchedulerService

    layout, trajectory_id, package = _setup(tmp_path)
    nonlocal_result = SchedulerService(layout).submit(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        variant_id=VARIANT_ID,
        package_path=str(package),
        backend="slurm",
        command="echo no",
    )
    assert nonlocal_result["ok"] is False
    assert nonlocal_result["error_type"] == "backend_not_implemented"

    (tmp_path / "repo" / "eval.py").write_text("print('tampered')\n", encoding="utf-8")
    blocked = SchedulerService(layout).submit(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        variant_id=VARIANT_ID,
        package_path=str(package),
        backend="local",
        command="echo no",
    )
    assert blocked["ok"] is False
    assert blocked["error_type"] == "protected_hash_mismatch"
