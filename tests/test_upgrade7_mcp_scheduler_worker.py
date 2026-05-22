from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload
from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

QUEST_ID = "QMCP_SCHED"
ENV_ID = "env_mcp_sched"
VARIANT_ID = "var_mcp_sched"


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
        "title": "MCP scheduler env",
        "problem": "mcp local scheduler",
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
        "executor": {"mcp_enabled": True},
    }
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True
    created = TrajectoryStore(layout).create(quest_id=QUEST_ID, env_id=ENV_ID, idea={"idea_id": "idea_mcp_sched", "title": "mcp scheduler idea"})
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


def _names(payload: dict) -> set[str]:
    return {tool["name"] for tool in payload["tools"]}


def test_scheduler_worker_tools_are_executor_only_not_planning_or_public_default(tmp_path: Path, monkeypatch):
    _setup(tmp_path)
    monkeypatch.setenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", "1")
    default_names = _names(tools_list_payload({}))
    planning_names = _names(tools_list_payload({"profile": "execution_planning"}))
    executor_names = _names(tools_list_payload({"profile": "executor_local", "project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID}))
    scheduler_worker = {"cs_scheduler_submit", "cs_scheduler_status", "cs_worker_claim", "cs_worker_heartbeat", "cs_worker_collect", "cs_worker_upload_artifact"}

    assert default_names.isdisjoint(scheduler_worker)
    assert planning_names.isdisjoint(scheduler_worker)
    assert scheduler_worker <= executor_names


def test_worker_claim_is_bound_to_requested_executor_env(tmp_path: Path, monkeypatch):
    from codex_scientist.services.scheduler import SchedulerService

    monkeypatch.setenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", "1")
    layout, trajectory_id, package = _setup(tmp_path)
    other_env = "env_mcp_sched_other"
    shown = EnvironmentService(layout).show(quest_id=QUEST_ID, env_id=ENV_ID)
    assert shown["ok"] is True, shown
    other_manifest = dict(shown["environment"])
    other_manifest["env_id"] = other_env
    other_manifest["executor"] = {"mcp_enabled": True}
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=other_manifest)["ok"] is True
    submitted = SchedulerService(layout).submit(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        variant_id=VARIANT_ID,
        package_path=str(package),
        backend="local",
        command=f"{sys.executable} -c \"print('should not claim')\"",
        expected_outputs=[],
    )
    assert submitted["ok"] is True, submitted

    claimed = call_tool("cs_worker_claim", {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": other_env, "worker_id": "w-cross"})

    assert claimed["ok"] is False, claimed
    assert claimed["error_type"] in {"empty_queue", "scope_mismatch"}


def test_mcp_scheduler_worker_round_trip_local_metrics(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", "1")
    layout, trajectory_id, package = _setup(tmp_path)
    command = f"{sys.executable} -c \"import json; json.dump({{'metrics': {{'score': 0.84}}}}, open('metrics.json','w'))\""
    submit = call_tool(
        "cs_scheduler_submit",
        {
            "project_root": str(tmp_path),
            "quest_id": QUEST_ID,
            "env_id": ENV_ID,
            "trajectory_id": trajectory_id,
            "variant_id": VARIANT_ID,
            "package_path": str(package),
            "backend": "local",
            "command": command,
            "expected_outputs": ["metrics.json"],
        },
    )
    assert submit["ok"] is True, submit
    claimed = call_tool("cs_worker_claim", {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "worker_id": "w1"})
    assert claimed["ok"] is True, claimed
    heartbeat = call_tool("cs_worker_heartbeat", {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "run_id": claimed["run"]["run_id"]})
    assert heartbeat["ok"] is True, heartbeat
    uploaded = call_tool(
        "cs_worker_upload_artifact",
        {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "job_id": submit["job"]["job_id"], "artifact_path": str(package), "kind": "package_manifest"},
    )
    assert uploaded["ok"] is True, uploaded
    assert Path(uploaded["artifact_ref"]["path"]).is_file()
    collected: dict = {"ok": False}
    for _ in range(30):
        collected = call_tool("cs_worker_collect", {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "job_id": submit["job"]["job_id"], "trusted_primary_metric": True})
        if collected.get("collected") is True and collected.get("job", {}).get("terminal") is True:
            break
        time.sleep(0.05)
    assert collected["ok"] is True, collected
    assert collected["feedback"]["primary_metric"]["value"] == 0.84
