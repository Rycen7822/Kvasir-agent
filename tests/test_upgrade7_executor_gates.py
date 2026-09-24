from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kvasir_agent.mcp.server import handle_jsonrpc_message
from kvasir_agent.services.environment import EnvironmentService
from kvasir_agent.services.project_state import ProjectLayout
from kvasir_agent.services.trajectory import TrajectoryStore

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
QUEST_ID = "QEXEC"
ENV_ID = "env_exec"

EXECUTOR_TOOLS = {
    "ka_variant_create",
    "ka_variant_apply_patch",
    "ka_variant_check",
    "ka_variant_pack",
    "ka_implementer_patch_check",
    "ka_implementer_repair_patch",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _make_repo(project_root: Path) -> tuple[Path, str]:
    repo = project_root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    if (repo / ".git").is_dir():
        return repo, _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    (repo / "train.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "evaluate.py").write_text("print('eval')\n", encoding="utf-8")
    (repo / "data.jsonl").write_text("{}\n", encoding="utf-8")
    _run(["git", "init"], repo)
    _run(["git", "add", "train.py", "evaluate.py", "data.jsonl"], repo)
    _run(["git", "-c", "user.name=Kvasir-agent", "-c", "user.email=kvasiragent@example.invalid", "commit", "-m", "baseline"], repo)
    return repo, _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()


def _manifest(
    project_root: Path,
    *,
    executor_mcp_enabled: bool = True,
    env_id: str = ENV_ID,
    gpu_count: int = 0,
    max_usd: float = 0.0,
    network_policy: str = "restricted",
    smoke_marker: str | None = None,
) -> dict:
    repo, commit = _make_repo(project_root)
    smoke_command = ["python", "-m", "py_compile", "train.py"]
    if smoke_marker:
        smoke_command = ["python", "-c", f"from pathlib import Path; Path({smoke_marker!r}).write_text('ran', encoding='utf-8')"]
    manifest = {
        "schema_version": 1,
        "env_id": env_id,
        "quest_id": QUEST_ID,
        "title": "Executor gate toy environment",
        "problem": "verify gated local variant execution",
        "baseline": {
            "repo_path": "repo",
            "commit": commit,
            "baseline_id": "baseline_exec",
            "baseline_metric": {"name": "score", "value": 0.5, "direction": "maximize"},
        },
        "mutable_allowlist": ["repo/train.py"],
        "protected_files": [{"path": "repo/evaluate.py", "sha256": _sha256(repo / "evaluate.py"), "role": "evaluator"}],
        "datasets": [{"path": "repo/data.jsonl", "sha256": _sha256(repo / "data.jsonl"), "split": "validation"}],
        "commands": {
            "setup": [["python", "-V"]],
            "smoke": [smoke_command],
            "run": [["python", "train.py"]],
            "evaluate": [["python", "evaluate.py"]],
        },
        "primary_metric": {"name": "score", "direction": "maximize", "parser": "json_path", "path": "metrics.score"},
        "sample_metrics": {"metrics": {"score": 0.5}},
        "secondary_metrics": [],
        "resources": {"gpu_count": gpu_count, "gpu_min_memory_gb": 0, "max_wall_time_sec": 60},
        "budget": {"max_gpu_hours": 0.0, "max_usd": max_usd},
        "security": {"network_policy": network_policy},
        "executor": {"mcp_enabled": executor_mcp_enabled},
    }
    return manifest


def _registered_executor_env(
    project_root: Path,
    *,
    executor_mcp_enabled: bool = True,
    env_id: str = ENV_ID,
    idea_id: str = "idea_exec",
    gpu_count: int = 0,
    max_usd: float = 0.0,
    network_policy: str = "restricted",
    smoke_marker: str | None = None,
) -> tuple[ProjectLayout, str]:
    layout = ProjectLayout.from_project_root(project_root)
    manifest = _manifest(
        project_root,
        executor_mcp_enabled=executor_mcp_enabled,
        env_id=env_id,
        gpu_count=gpu_count,
        max_usd=max_usd,
        network_policy=network_policy,
        smoke_marker=smoke_marker,
    )
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True
    trajectory = TrajectoryStore(layout).create(
        quest_id=QUEST_ID,
        env_id=env_id,
        idea={"idea_id": idea_id, "title": "Executor variant"},
        strategy="manual",
    )
    assert trajectory["ok"] is True
    return layout, trajectory["trajectory_id"]


def test_implementer_patch_check_rejects_protected_file_patch_before_git_apply_ok(tmp_path: Path):
    from kvasir_agent.runtime import tools

    _layout, trajectory_id = _registered_executor_env(tmp_path)
    created = json.loads(
        tools.ka_variant_create(
            {
                "project_root": str(tmp_path),
                "quest_id": QUEST_ID,
                "env_id": ENV_ID,
                "trajectory_id": trajectory_id,
                "idea_id": "idea_exec",
                "approved": True,
            }
        )
    )
    assert created["ok"] is True, created
    patch_path = tmp_path / "protected.diff"
    patch_path.write_text(
        "diff --git a/evaluate.py b/evaluate.py\n"
        "--- a/evaluate.py\n"
        "+++ b/evaluate.py\n"
        "@@ -1 +1 @@\n"
        "-print('eval')\n"
        "+print('changed')\n",
        encoding="utf-8",
    )

    checked = json.loads(
        tools.ka_implementer_patch_check(
            {
                "project_root": str(tmp_path),
                "quest_id": QUEST_ID,
                "env_id": ENV_ID,
                "variant_id": created["variant_id"],
                "patch_path": str(patch_path),
                "approved": True,
            }
        )
    )

    assert checked["ok"] is False, checked
    assert checked["error_type"] == "readonly_or_eval_changed"
    assert "evaluate.py" in checked.get("blocked_paths", [])


@pytest.mark.parametrize(
    ("tool_name", "extra"),
    [
        ("ka_variant_apply_patch", {"patch_path": "change.diff"}),
        ("ka_variant_check", {}),
        ("ka_variant_pack", {}),
        ("ka_implementer_patch_check", {"patch_path": "change.diff"}),
        ("ka_implementer_repair_patch", {"failure": {"error_type": "smoke_fail"}}),
    ],
)
def test_variant_bound_local_only_gate_rejects_mismatched_env_id_before_execution(tmp_path: Path, tool_name: str, extra: dict):
    from kvasir_agent.runtime import tools

    _registered_executor_env(tmp_path, env_id=ENV_ID, idea_id="idea_zero")
    _layout, high_trajectory_id = _registered_executor_env(
        tmp_path,
        env_id="env_high",
        idea_id="idea_high",
        gpu_count=8,
        max_usd=100.0,
        network_policy="open",
        smoke_marker="HIGH_SMOKE_RAN",
    )
    created = json.loads(
        tools.ka_variant_create(
            {
                "project_root": str(tmp_path),
                "quest_id": QUEST_ID,
                "env_id": "env_high",
                "trajectory_id": high_trajectory_id,
                "idea_id": "idea_high",
                "approved": True,
            }
        )
    )
    assert created["ok"] is True, created
    patch_path = tmp_path / "change.diff"
    patch_path.write_text(
        "diff --git a/train.py b/train.py\n"
        "--- a/train.py\n"
        "+++ b/train.py\n"
        "@@ -1 +1 @@\n"
        "-VALUE = 1\n"
        "+VALUE = 2\n",
        encoding="utf-8",
    )

    call_extra = dict(extra)
    if call_extra.get("patch_path") == "change.diff":
        call_extra["patch_path"] = str(patch_path)
    payload = {
        "project_root": str(tmp_path),
        "quest_id": QUEST_ID,
        "variant_id": created["variant_id"],
        "local_only": True,
        "env_id": ENV_ID,
        **call_extra,
    }
    result = json.loads(getattr(tools, tool_name)(payload))

    assert result["ok"] is False
    assert result["error_type"] == "executor_gate_env_mismatch"
    assert result["variant_env_id"] == "env_high"
    assert result["provided_env_id"] == ENV_ID
    assert not (Path(created["workspace_path"]) / "HIGH_SMOKE_RAN").exists()
