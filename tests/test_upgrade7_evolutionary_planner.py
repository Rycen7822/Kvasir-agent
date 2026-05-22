from __future__ import annotations

import hashlib
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.method_improvement import MethodImprovementService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

QUEST_ID = "QEVO"
ENV_ID = "env_evo"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _register_env(tmp_path: Path, *, env_id: str = ENV_ID, direction: str = "maximize", baseline_value: float = 0.5) -> ProjectLayout:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "train.py").write_text("print('train')\n", encoding="utf-8")
    (repo / "evaluate.py").write_text("print('eval')\n", encoding="utf-8")
    (repo / "data.jsonl").write_text("{}\n", encoding="utf-8")
    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = {
        "schema_version": 1,
        "env_id": env_id,
        "quest_id": QUEST_ID,
        "title": "Evolutionary env",
        "problem": "plan only evolutionary round",
        "baseline": {"repo_path": "repo", "baseline_metric": {"name": "score", "value": baseline_value, "direction": direction}},
        "mutable_allowlist": ["repo/train.py"],
        "protected_files": [{"path": "repo/evaluate.py", "sha256": _sha256(repo / "evaluate.py"), "role": "evaluator"}],
        "datasets": [{"path": "repo/data.jsonl", "sha256": _sha256(repo / "data.jsonl"), "split": "validation"}],
        "commands": {"setup": [["python", "-V"]], "smoke": [["python", "-m", "py_compile", "train.py"]], "run": [["python", "train.py"]], "evaluate": [["python", "evaluate.py"]]},
        "primary_metric": {"name": "score", "direction": direction, "parser": "json_path", "path": "metrics.score"},
        "sample_metrics": {"metrics": {"score": baseline_value}},
        "resources": {"gpu_count": 0},
        "budget": {"max_gpu_hours": 0.0, "max_usd": 0.0},
        "security": {"network_policy": "restricted"},
    }
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True
    return layout


def _trajectory(
    layout: ProjectLayout,
    *,
    env_id: str = ENV_ID,
    idea_id: str,
    mechanism_family: str,
    metric_value: float,
    direction: str = "maximize",
    trusted: bool = True,
    protected_ok: bool = True,
    status: str = "evaluated",
) -> str:
    store = TrajectoryStore(layout)
    created = store.create(
        quest_id=QUEST_ID,
        env_id=env_id,
        idea={"idea_id": idea_id, "title": idea_id, "mechanism_family": mechanism_family, "novelty_rationale": "distinct"},
        strategy="manual",
    )
    assert created["ok"] is True, created
    trajectory_id = created["trajectory_id"]
    assert store.update_patch(quest_id=QUEST_ID, trajectory_id=trajectory_id, patch={"protected_hashes_ok": protected_ok})["ok"] is True
    assert store.update_result(
        quest_id=QUEST_ID,
        trajectory_id=trajectory_id,
        result={
            "status": status,
            "primary_metric": {"name": "score", "value": metric_value, "direction": direction},
            "trusted_primary_metric": trusted,
        },
    )["ok"] is True
    return trajectory_id


def test_evolutionary_planner_selects_positive_parents_by_metric_direction(tmp_path: Path):
    from codex_scientist.services.evolutionary import EvolutionarySearchService

    layout = _register_env(tmp_path, direction="minimize", baseline_value=1.0)
    good = _trajectory(layout, idea_id="good", mechanism_family="optimizer", metric_value=0.7, direction="minimize")
    bad = _trajectory(layout, idea_id="bad", mechanism_family="worse", metric_value=1.2, direction="minimize")

    plan = EvolutionarySearchService(layout).plan_round(quest_id=QUEST_ID, env_id=ENV_ID, epoch=1, batch_size=4)

    assert plan["ok"] is True, plan
    parent_ids = [item["trajectory_id"] for item in plan["round_plan"]["exploit_parents"]]
    assert good in parent_ids
    assert bad not in parent_ids
    assert plan["round_plan"]["submit_allowed"] is False


def test_evolutionary_planner_excludes_protected_hash_failures(tmp_path: Path):
    from codex_scientist.services.evolutionary import EvolutionarySearchService

    layout = _register_env(tmp_path)
    good = _trajectory(layout, idea_id="good", mechanism_family="adapter", metric_value=0.8, protected_ok=True)
    tampered = _trajectory(layout, idea_id="tamper", mechanism_family="eval_tamper", metric_value=0.9, protected_ok=False)

    plan = EvolutionarySearchService(layout).plan_round(quest_id=QUEST_ID, env_id=ENV_ID, epoch=1, batch_size=4)

    parent_ids = [item["trajectory_id"] for item in plan["round_plan"]["exploit_parents"]]
    assert good in parent_ids
    assert tampered not in parent_ids
    assert "protected_hash_mismatch" in plan["round_plan"]["negative_signals"]


def test_evolutionary_planner_marks_duplicate_negative_mechanisms_as_risky(tmp_path: Path):
    from codex_scientist.services.evolutionary import EvolutionarySearchService

    layout = _register_env(tmp_path)
    MethodImprovementService(layout).record_negative_result(
        quest_id=QUEST_ID,
        trial_id="T-old",
        idea_id="I-old",
        failure_reason="regressed",
        lesson="avoid widening layer blindly",
        mechanism="widening layer blindly",
    )

    plan = EvolutionarySearchService(layout).plan_round(quest_id=QUEST_ID, env_id=ENV_ID, epoch=1, batch_size=4)

    risks = plan["round_plan"]["risk_flags"]
    assert any(item["risk"] == "duplicate_negative_memory" and item["mechanism_family"] == "widening layer blindly" for item in risks)
    assert all(candidate.get("mechanism_family") != "widening layer blindly" for candidate in plan["round_plan"]["candidates"])


def test_evolutionary_planner_diversity_quota_prevents_family_collapse(tmp_path: Path):
    from codex_scientist.services.evolutionary import EvolutionarySearchService

    layout = _register_env(tmp_path)
    for index in range(6):
        _trajectory(layout, idea_id=f"adapter-{index}", mechanism_family="adapter", metric_value=0.9 - index * 0.01)
    _trajectory(layout, idea_id="optimizer-1", mechanism_family="optimizer", metric_value=0.82)

    plan = EvolutionarySearchService(layout).plan_round(quest_id=QUEST_ID, env_id=ENV_ID, epoch=3, batch_size=8)

    counts = plan["round_plan"]["diversity"]["mechanism_family_counts"]
    assert counts["adapter"] <= 2
    assert plan["round_plan"]["diversity"]["max_same_mechanism_family_fraction"] <= 0.25


def test_evolutionary_planner_is_plan_only_and_never_creates_executor_state(tmp_path: Path):
    from codex_scientist.services.evolutionary import EvolutionarySearchService

    layout = _register_env(tmp_path)
    _trajectory(layout, idea_id="good", mechanism_family="adapter", metric_value=0.8)

    plan = EvolutionarySearchService(layout).plan_round(quest_id=QUEST_ID, env_id=ENV_ID, epoch=1, batch_size=4)

    assert plan["round_plan"]["submit_allowed"] is False
    quest_root = tmp_path / "CodexScientist" / "quests" / QUEST_ID
    assert not any((quest_root / "variants").glob("*/variant.json"))
    assert not any((quest_root / "runtime" / "queue").glob("*.json"))
