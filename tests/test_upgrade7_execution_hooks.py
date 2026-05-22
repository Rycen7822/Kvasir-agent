from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.execution_hooks import ExecutionHooksService
from codex_scientist.services.feedback_ingest import FeedbackIngestService
from codex_scientist.services.method_improvement import MethodImprovementService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

QUEST_ID = "QHOOK"
ENV_ID = "env_hook"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup(tmp_path: Path, *, idea_id: str = "idea_hook") -> tuple[ProjectLayout, str, Path]:
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
        "title": "Hook env",
        "problem": "feedback hook",
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
    created = TrajectoryStore(layout).create(quest_id=QUEST_ID, env_id=ENV_ID, idea={"idea_id": idea_id, "mechanism_family": "adapter"})
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"metrics": {"score": 0.75}}), encoding="utf-8")
    return layout, created["trajectory_id"], metrics


def test_feedback_ingest_hook_updates_scoreboard_frontier_and_cached_claimability(tmp_path: Path):
    layout, trajectory_id, metrics = _setup(tmp_path)
    feedback = FeedbackIngestService(layout).ingest(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        run_id="RHOOK1",
        source_kind="local_metrics",
        metrics_path=str(metrics),
        trusted_primary_metric=True,
    )
    assert feedback["ok"] is True, feedback

    scoreboard = json.loads(MethodImprovementService(layout).scoreboard_path(QUEST_ID).read_text(encoding="utf-8"))
    assert scoreboard["ideas"]["idea_hook"]["outcome"] == "positive"
    assert scoreboard["ideas"]["idea_hook"]["metric_delta"] == 0.25
    trajectory = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["claimability"]["claim_gate_status"] == "candidate"
    assert trajectory["claimability"]["source"] == "feedback_hook"


def test_invalid_local_metrics_are_not_trusted_or_claimable(tmp_path: Path):
    layout, trajectory_id, metrics = _setup(tmp_path, idea_id="idea_bad_metric")
    metrics.write_text(json.dumps({"metrics": {"other": 0.75}}), encoding="utf-8")

    feedback = FeedbackIngestService(layout).ingest(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        run_id="RHOOK_BAD",
        source_kind="local_metrics",
        metrics_path=str(metrics),
        trusted_primary_metric=True,
    )

    assert feedback["ok"] is True, feedback
    assert feedback["feedback"]["status"] in {"metric_missing", "metric_invalid"}
    assert feedback["feedback"]["trusted_primary_metric"] is False
    trajectory = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["result"]["trusted_primary_metric"] is False
    assert trajectory["claimability"]["claim_gate_status"] == "needs_revalidation"
    scoreboard_path = MethodImprovementService(layout).scoreboard_path(QUEST_ID)
    if scoreboard_path.exists():
        scoreboard = json.loads(scoreboard_path.read_text(encoding="utf-8"))
        assert "idea_bad_metric" not in scoreboard.get("ideas", {})


def test_direct_hook_rejects_inconsistent_trusted_invalid_metric(tmp_path: Path):
    layout, trajectory_id, _metrics = _setup(tmp_path, idea_id="idea_inconsistent_hook")

    hook = ExecutionHooksService(layout).on_feedback_ingested(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        feedback={"run_id": "RHOOK_INCONSISTENT", "status": "metric_invalid", "trusted_primary_metric": True, "primary_metric": None},
        feedback_path=str(tmp_path / "feedback.json"),
    )

    assert hook["ok"] is True, hook
    trajectory = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["claimability"]["claim_gate_status"] == "needs_revalidation"
    assert "metric_invalid" in trajectory["claimability"]["blocking_reasons"]
    scoreboard_path = MethodImprovementService(layout).scoreboard_path(QUEST_ID)
    if scoreboard_path.exists():
        scoreboard = json.loads(scoreboard_path.read_text(encoding="utf-8"))
        assert "idea_inconsistent_hook" not in scoreboard.get("ideas", {})


def test_direct_hook_rejects_inconsistent_trusted_nonfinite_metric(tmp_path: Path):
    layout, trajectory_id, _metrics = _setup(tmp_path, idea_id="idea_nonfinite_hook")

    hook = ExecutionHooksService(layout).on_feedback_ingested(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        feedback={"run_id": "RHOOK_INF", "status": "parsed", "trusted_primary_metric": True, "primary_metric": {"name": "score", "value": "inf", "direction": "maximize"}},
        feedback_path=str(tmp_path / "feedback.json"),
    )

    assert hook["ok"] is True, hook
    trajectory = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["claimability"]["claim_gate_status"] == "needs_revalidation"
    assert "metric_invalid" in trajectory["claimability"]["blocking_reasons"]
    scoreboard_path = MethodImprovementService(layout).scoreboard_path(QUEST_ID)
    if scoreboard_path.exists():
        scoreboard = json.loads(scoreboard_path.read_text(encoding="utf-8"))
        assert "idea_nonfinite_hook" not in scoreboard.get("ideas", {})


def test_untrusted_feedback_hook_marks_revalidation_not_claimable(tmp_path: Path):
    layout, trajectory_id, metrics = _setup(tmp_path, idea_id="idea_untrusted")
    feedback = FeedbackIngestService(layout).ingest(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        run_id="RHOOK2",
        source_kind="manual",
        metrics_path=str(metrics),
        trusted_primary_metric=True,
    )
    assert feedback["ok"] is True, feedback
    trajectory = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["result"]["trusted_primary_metric"] is False
    assert trajectory["claimability"]["claim_gate_status"] == "needs_revalidation"
    scoreboard_path = MethodImprovementService(layout).scoreboard_path(QUEST_ID)
    if scoreboard_path.exists():
        scoreboard = json.loads(scoreboard_path.read_text(encoding="utf-8"))
        assert "idea_untrusted" not in scoreboard.get("ideas", {})
