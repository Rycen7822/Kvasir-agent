from __future__ import annotations

import hashlib
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload
from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

QUEST_ID = "QEVOMCP"
ENV_ID = "env_evo_mcp"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _register_env(tmp_path: Path) -> ProjectLayout:
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
        "title": "MCP evolutionary env",
        "problem": "plan-only mcp evolutionary round",
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
    created = TrajectoryStore(layout).create(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        idea={"idea_id": "idea_mcp", "title": "MCP idea", "mechanism_family": "adapter"},
    )
    assert created["ok"] is True, created
    assert TrajectoryStore(layout).update_patch(quest_id=QUEST_ID, trajectory_id=created["trajectory_id"], patch={"protected_hashes_ok": True})["ok"] is True
    assert TrajectoryStore(layout).update_result(
        quest_id=QUEST_ID,
        trajectory_id=created["trajectory_id"],
        result={"status": "evaluated", "trusted_primary_metric": True, "primary_metric": {"name": "score", "value": 0.8, "direction": "maximize"}},
    )["ok"] is True
    return layout


def test_execution_planning_profile_exposes_plan_only_evolutionary_tool():
    listed = tools_list_payload({"profile": "execution_planning"})
    tool_names = {tool["name"] for tool in listed["tools"]}
    assert "cs_evolutionary_plan_round" in tool_names
    assert "cs_evolutionary_round_submit" not in tool_names


def test_mcp_evolutionary_plan_round_is_plan_only_and_writes_round_artifact(tmp_path: Path):
    _register_env(tmp_path)

    planned = call_tool(
        "cs_evolutionary_plan_round",
        {"project": str(tmp_path), "quest_id": QUEST_ID, "env_id": ENV_ID, "epoch": 2, "batch_size": 4},
    )

    assert planned["ok"] is True, planned
    assert planned["mcp"] is True
    assert planned["round_plan"]["round_id"] == "round_0002"
    assert planned["round_plan"]["submit_allowed"] is False
    assert planned["round_plan"]["executor_side_effects"] is False
    assert planned["round_plan"]["exploit_parents"][0]["idea_id"] == "idea_mcp"
    assert Path(planned["path"]).is_file()
    quest_root = tmp_path / "CodexScientist" / "quests" / QUEST_ID
    assert not any((quest_root / "variants").glob("*/variant.json"))
    assert not any((quest_root / "runtime" / "queue").glob("*.json"))


def test_default_mcp_rejects_evolutionary_round_submit_by_default(tmp_path: Path):
    payload = call_tool("cs_evolutionary_round_submit", {"project": str(tmp_path), "quest_id": QUEST_ID, "round_id": "round_0001"})
    assert payload["ok"] is False
    assert payload["error_type"] in {"unknown_tool", "tool_not_registered_for_mcp", "internal_error", "executor_gate_required", "executor_mcp_disabled"}
