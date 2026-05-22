from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.feedback_ingest import FeedbackIngestService
from codex_scientist.services.method_improvement import MethodImprovementService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

QUEST_ID = "QCLAIMLINK"
ENV_ID = "env_claimlink"


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
        "title": "Claim link env",
        "problem": "claim link",
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
    created = TrajectoryStore(layout).create(quest_id=QUEST_ID, env_id=ENV_ID, idea={"idea_id": "idea_claimlink", "mechanism_family": "optimizer"})
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({"metrics": {"score": 0.8}}), encoding="utf-8")
    return layout, created["trajectory_id"], metrics


def test_trajectory_claimability_is_cached_summary_not_claim_gate_authority(tmp_path: Path):
    layout, trajectory_id, metrics = _setup(tmp_path)
    feedback = FeedbackIngestService(layout).ingest(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        trajectory_id=trajectory_id,
        run_id="RCLAIM1",
        source_kind="local_metrics",
        metrics_path=str(metrics),
        trusted_primary_metric=True,
    )
    assert feedback["ok"] is True, feedback
    trajectory = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["claimability"]["claim_gate_status"] == "candidate"
    assert trajectory["claimability"]["source"] == "feedback_hook"

    gate = MethodImprovementService(layout).claim_gate(
        quest_id=QUEST_ID,
        claim_id="claim_from_trajectory",
        claim_text="Optimizer improves score.",
        baseline_id=None,
        metric_contract="score json_path metrics.score",
        evidence_paths=[feedback["path"]],
        analysis_slice_ids=[],
        seed_count=1,
    )
    assert gate["ok"] is False
    assert gate["error_type"] == "claim_gate_blocked"
    assert "baseline_missing" in gate["blocking_reasons"]
    refreshed = TrajectoryStore(layout).show(quest_id=QUEST_ID, trajectory_id=trajectory_id)["trajectory"]
    assert refreshed["claimability"]["claim_gate_status"] == "candidate"
