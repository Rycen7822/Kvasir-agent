from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from codex_scientist.mcp.server import handle_jsonrpc_message
from codex_scientist.mcp.tool_registry import tools_list_payload
from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
QUEST_ID = "QEXEC"
ENV_ID = "env_exec"

EXECUTOR_TOOLS = {
    "cs_variant_create",
    "cs_variant_apply_patch",
    "cs_variant_check",
    "cs_variant_pack",
    "cs_implementer_patch_check",
    "cs_implementer_repair_patch",
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
    _run(["git", "-c", "user.name=CodexScientist", "-c", "user.email=codexscientist@example.invalid", "commit", "-m", "baseline"], repo)
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


def _cli(project_root: Path, tool_name: str, payload: dict) -> tuple[int, dict]:
    result = subprocess.run(
        [
            PYTHON,
            str(REPO_ROOT / "scripts" / "cs_native_cli.py"),
            "--project-root",
            str(project_root),
            "call",
            tool_name,
            "--json",
            json.dumps(payload),
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - assertion helper
        raise AssertionError(result.stderr + result.stdout) from exc
    return result.returncode, parsed


def _variant_create_payload(trajectory_id: str, **extra: object) -> dict:
    payload: dict[str, object] = {"quest_id": QUEST_ID, "env_id": ENV_ID, "trajectory_id": trajectory_id, "idea_id": "idea_exec"}
    payload.update(extra)
    return payload


def test_default_mcp_tools_list_and_call_fail_closed_for_executor_tools():
    names = {tool["name"] for tool in tools_list_payload({})["tools"]}
    assert names.isdisjoint(EXECUTOR_TOOLS), sorted(names & EXECUTOR_TOOLS)

    response = handle_jsonrpc_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "cs_variant_create", "arguments": {}}}
    )
    assert response is not None
    structured = response["result"]["structuredContent"]
    assert structured["ok"] is False
    assert structured["error_type"] == "tool_not_registered_for_mcp"
    assert structured["tool"] == "cs_variant_create"


def test_executor_mcp_profile_requires_env_var_and_manifest_flag(tmp_path: Path, monkeypatch):
    _registered_executor_env(tmp_path, executor_mcp_enabled=False)

    no_env = tools_list_payload({"profile": "executor_local", "project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID})
    assert no_env["ok"] is False
    assert no_env["error_type"] == "executor_mcp_disabled"

    monkeypatch.setenv("CODEXSCIENTIST_ENABLE_EXECUTOR_MCP", "1")
    no_manifest_flag = tools_list_payload({"profile": "executor_local", "project_root": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID})
    assert no_manifest_flag["ok"] is False
    assert no_manifest_flag["error_type"] == "executor_mcp_manifest_required"

    enabled_project = tmp_path / "enabled"
    _registered_executor_env(enabled_project, executor_mcp_enabled=True)
    listed = tools_list_payload({"profile": "executor_local", "project_root": str(enabled_project), "quest_id": QUEST_ID, "env_id": ENV_ID})
    assert listed["ok"] is True, listed
    names = {tool["name"] for tool in listed["tools"]}
    assert EXECUTOR_TOOLS <= names


def test_cli_executor_variant_create_requires_approval_or_local_only_gate(tmp_path: Path):
    _layout, trajectory_id = _registered_executor_env(tmp_path)

    returncode, blocked = _cli(tmp_path, "cs_variant_create", _variant_create_payload(trajectory_id, approved=False))

    assert returncode == 1
    assert blocked["ok"] is False
    assert blocked["error_type"] == "executor_gate_required"
    assert blocked["required_approval"] == "approved=true"


def test_cli_executor_scheduler_submit_requires_approval_or_local_only_gate(tmp_path: Path):
    _layout, trajectory_id = _registered_executor_env(tmp_path)

    returncode, blocked = _cli(
        tmp_path,
        "cs_scheduler_submit",
        {
            "quest_id": QUEST_ID,
            "env_id": ENV_ID,
            "trajectory_id": trajectory_id,
            "variant_id": "var_cli_gate",
            "package_path": str(tmp_path / "missing-package.json"),
            "command": "echo should-not-run",
        },
    )

    assert returncode == 1
    assert blocked["ok"] is False
    assert blocked["error_type"] == "executor_gate_required"


def test_cli_executor_internal_mcp_marker_cannot_be_forged(tmp_path: Path):
    _layout, trajectory_id = _registered_executor_env(tmp_path)

    returncode, blocked = _cli(
        tmp_path,
        "cs_scheduler_submit",
        {
            "quest_id": QUEST_ID,
            "env_id": ENV_ID,
            "trajectory_id": trajectory_id,
            "variant_id": "var_mcp_forged",
            "package_path": str(tmp_path / "missing-package.json"),
            "command": "echo should-not-run",
            "_mcp_executor_gate_passed": True,
        },
    )

    assert returncode == 1
    assert blocked["ok"] is False
    assert blocked["error_type"] == "executor_gate_required"


def test_implementer_patch_check_rejects_protected_file_patch_before_git_apply_ok(tmp_path: Path):
    from codex_scientist.runtime import tools

    _layout, trajectory_id = _registered_executor_env(tmp_path)
    created = json.loads(
        tools.cs_variant_create(
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
        tools.cs_implementer_patch_check(
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


def test_cli_executor_approved_variant_create_succeeds_on_zero_cost_toy_repo(tmp_path: Path):
    _layout, trajectory_id = _registered_executor_env(tmp_path)

    returncode, created = _cli(tmp_path, "cs_variant_create", _variant_create_payload(trajectory_id, approved=True))

    assert returncode == 0, created
    assert created["ok"] is True
    assert created["variant_id"].startswith("var_")
    assert Path(created["workspace_path"]).is_dir()


def test_cli_executor_local_only_gate_succeeds_without_approval_for_zero_cost_env(tmp_path: Path):
    _layout, trajectory_id = _registered_executor_env(tmp_path)

    returncode, created = _cli(tmp_path, "cs_variant_create", _variant_create_payload(trajectory_id, local_only=True))

    assert returncode == 0, created
    assert created["ok"] is True
    assert created["executor_gate"]["decision"] == "local_only_allowed"
    assert created["variant_id"].startswith("var_")


@pytest.mark.parametrize(
    ("tool_name", "extra"),
    [
        ("cs_variant_apply_patch", {"patch_path": "change.diff"}),
        ("cs_variant_check", {}),
        ("cs_variant_pack", {}),
        ("cs_implementer_patch_check", {"patch_path": "change.diff"}),
        ("cs_implementer_repair_patch", {"failure": {"error_type": "smoke_fail"}}),
    ],
)
def test_variant_bound_local_only_gate_rejects_mismatched_env_id_before_execution(tmp_path: Path, tool_name: str, extra: dict):
    from codex_scientist.runtime import tools

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
        tools.cs_variant_create(
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
