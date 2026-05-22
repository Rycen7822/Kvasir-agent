from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool
from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.evolutionary import EvolutionarySearchService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.queue import QueueService
from codex_scientist.services.trajectory import TrajectoryStore

QUEST_ID = "QROUND"
ENV_ID = "env_round"
VARIANT_ID = "var_round"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup(tmp_path: Path) -> tuple[ProjectLayout, str, str, Path]:
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
        "title": "Round env",
        "problem": "round submit",
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
    created = TrajectoryStore(layout).create(quest_id=QUEST_ID, env_id=ENV_ID, idea={"idea_id": "idea_round", "mechanism_family": "adapter"})
    trajectory_id = created["trajectory_id"]
    plan = EvolutionarySearchService(layout).plan_round(quest_id=QUEST_ID, env_id=ENV_ID, epoch=0, batch_size=2)
    assert plan["ok"] is True, plan
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
    return layout, plan["round_id"], trajectory_id, package


def test_direct_executor_round_submit_requires_mcp_gate(tmp_path: Path, monkeypatch):
    _layout, round_id, trajectory_id, package = _setup(tmp_path)
    monkeypatch.delenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", raising=False)

    result = call_tool(
        "cs_evolutionary_round_submit",
        {
            "project_root": str(tmp_path),
            "quest_id": QUEST_ID,
            "env_id": ENV_ID,
            "round_id": round_id,
            "submissions": [{"candidate_id": "cand_0000_001", "variant_id": VARIANT_ID, "trajectory_id": trajectory_id, "package_path": str(package), "command": "echo no"}],
            "approval": {"approved": True, "budget_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()},
        },
    )

    assert result["ok"] is False
    assert result["error_type"] == "executor_mcp_disabled"


def test_evolutionary_round_submit_uses_existing_plan_and_scheduler(tmp_path: Path, monkeypatch):
    _layout, round_id, trajectory_id, package = _setup(tmp_path)
    monkeypatch.setenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", "1")
    command = f"{sys.executable} -c \"import json; json.dump({{'metrics': {{'score': 0.9}}}}, open('metrics.json','w'))\""

    submitted = call_tool(
        "cs_evolutionary_round_submit",
        {
            "project_root": str(tmp_path),
            "quest_id": QUEST_ID,
            "env_id": ENV_ID,
            "round_id": round_id,
            "approval": {"approved": True, "budget_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()},
            "submissions": [
                {
                    "candidate_id": "cand_0000_001",
                    "variant_id": VARIANT_ID,
                    "trajectory_id": trajectory_id,
                    "package_path": str(package),
                    "command": command,
                    "expected_outputs": ["metrics.json"],
                }
            ],
        },
    )

    assert submitted["ok"] is True, submitted
    assert submitted["round_id"] == round_id
    assert submitted["submitted_jobs"][0]["resource"]["variant_id"] == VARIANT_ID
    variant_dir = tmp_path / "details" / QUEST_ID / "variants"
    assert not variant_dir.exists(), "round submit must not create variants; it only submits existing packages"


def test_evolutionary_round_submit_does_not_allow_repeat_without_new_approval(tmp_path: Path, monkeypatch):
    _layout, round_id, trajectory_id, package = _setup(tmp_path)
    monkeypatch.setenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", "1")
    approved = {"approved": True, "budget_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()}
    submission = {
        "candidate_id": "cand_0000_001",
        "variant_id": VARIANT_ID,
        "trajectory_id": trajectory_id,
        "package_path": str(package),
        "command": f"{sys.executable} -c \"print('once')\"",
    }
    first = call_tool(
        "cs_evolutionary_round_submit",
        {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "round_id": round_id, "approval": approved, "submissions": [submission]},
    )
    assert first["ok"] is True, first

    second = call_tool(
        "cs_evolutionary_round_submit",
        {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "round_id": round_id, "submissions": [submission]},
    )

    assert second["ok"] is False, second
    assert second["error_type"] in {"round_already_submitted", "approval_required"}


def test_evolutionary_round_submit_rejects_duplicate_or_existing_jobs_before_partial_submit(tmp_path: Path, monkeypatch):
    layout, round_id, trajectory_id, package = _setup(tmp_path)
    monkeypatch.setenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", "1")
    approved = {"approved": True, "budget_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()}
    submission = {
        "candidate_id": "cand_0000_001",
        "variant_id": VARIANT_ID,
        "trajectory_id": trajectory_id,
        "package_path": str(package),
        "command": f"{sys.executable} -c \"print('duplicate')\"",
    }

    duplicate = call_tool(
        "cs_evolutionary_round_submit",
        {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "round_id": round_id, "approval": approved, "submissions": [submission, dict(submission)]},
    )

    assert duplicate["ok"] is False, duplicate
    assert duplicate["error_type"] == "duplicate_round_submission"
    assert QueueService(layout).status()["jobs"] == {}

    whitespace_submission = dict(submission)
    whitespace_submission["variant_id"] = f" {VARIANT_ID} "
    whitespace_duplicate = call_tool(
        "cs_evolutionary_round_submit",
        {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "round_id": round_id, "approval": approved, "submissions": [submission, whitespace_submission]},
    )

    assert whitespace_duplicate["ok"] is False, whitespace_duplicate
    assert whitespace_duplicate["error_type"] == "duplicate_round_submission"
    assert QueueService(layout).status()["jobs"] == {}

    preexisting = QueueService(layout).submit(
        job_id=f"job_{VARIANT_ID}",
        command="echo preexisting",
        resource={"quest_id": QUEST_ID, "env_id": ENV_ID, "trajectory_id": trajectory_id, "variant_id": VARIANT_ID, "package_path": str(package), "backend": "local", "expected_outputs": []},
    )
    assert preexisting["ok"] is True
    existing = call_tool(
        "cs_evolutionary_round_submit",
        {"project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "round_id": round_id, "approval": approved, "submissions": [submission]},
    )

    assert existing["ok"] is False, existing
    assert existing["error_type"] == "round_job_exists"
    assert QueueService(layout).status()["jobs"][f"job_{VARIANT_ID}"]["command"] == "echo preexisting"


def test_evolutionary_round_submit_prevalidates_batch_without_partial_jobs(tmp_path: Path, monkeypatch):
    layout, round_id, trajectory_id, package = _setup(tmp_path)
    monkeypatch.setenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", "1")
    bad_package = tmp_path / "missing-package.json"
    result = call_tool(
        "cs_evolutionary_round_submit",
        {
            "project_root": str(tmp_path),
            "quest_id": QUEST_ID,
            "env_id": ENV_ID,
            "round_id": round_id,
            "approval": {"approved": True, "budget_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()},
            "submissions": [
                {
                    "candidate_id": "cand_0000_001",
                    "variant_id": VARIANT_ID,
                    "trajectory_id": trajectory_id,
                    "package_path": str(package),
                    "command": f"{sys.executable} -c \"print('valid')\"",
                },
                {
                    "candidate_id": "cand_0000_002",
                    "variant_id": "var_round_bad",
                    "trajectory_id": trajectory_id,
                    "package_path": str(bad_package),
                    "command": f"{sys.executable} -c \"print('invalid')\"",
                },
            ],
        },
    )

    assert result["ok"] is False, result
    assert result["error_type"] in {"invalid_path", "package_mismatch", "missing_argument"}
    assert QueueService(layout).status()["jobs"] == {}
