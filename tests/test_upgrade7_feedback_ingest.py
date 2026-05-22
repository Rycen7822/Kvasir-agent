from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore

from test_upgrade7_environment_service import _valid_manifest


def _setup(tmp_path: Path) -> tuple[ProjectLayout, str]:
    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _valid_manifest(tmp_path, quest_id="QFEED")
    assert EnvironmentService(layout).register(quest_id="QFEED", manifest=manifest)["ok"] is True
    trajectory_id = TrajectoryStore(layout).create(quest_id="QFEED", env_id="env_toy", idea={"idea_id": "idea_1", "title": "Idea"})["trajectory_id"]
    return layout, trajectory_id


def test_feedback_ingest_local_metrics_updates_trajectory(tmp_path: Path):
    from codex_scientist.services.feedback_ingest import FeedbackIngestService

    layout, trajectory_id = _setup(tmp_path)
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"metrics": {"eval": {"mean_reward": 0.8}}}), encoding="utf-8")

    result = FeedbackIngestService(layout).ingest(
        quest_id="QFEED",
        env_id="env_toy",
        trajectory_id=trajectory_id,
        run_id="run_good",
        source_kind="local_metrics",
        metrics_path=str(metrics_path),
        trusted_primary_metric=True,
    )

    assert result["ok"] is True
    assert result["feedback"]["status"] == "parsed"
    assert result["feedback"]["primary_metric"]["value"] == 0.8
    bundle_path = tmp_path / "CodexScientist" / "quests" / "QFEED" / "artifacts" / "execution_grounded" / "run_good" / "feedback_bundle.json"
    assert bundle_path.exists()

    trajectory = TrajectoryStore(layout).show(quest_id="QFEED", trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["result"]["status"] == "evaluated"
    assert trajectory["result"]["trusted_primary_metric"] is True


def test_feedback_ingest_missing_metric_records_metric_missing_failure(tmp_path: Path):
    from codex_scientist.services.feedback_ingest import FeedbackIngestService

    layout, trajectory_id = _setup(tmp_path)
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"metrics": {"eval": {}}}), encoding="utf-8")

    result = FeedbackIngestService(layout).ingest(
        quest_id="QFEED",
        env_id="env_toy",
        trajectory_id=trajectory_id,
        run_id="run_missing",
        source_kind="local_metrics",
        metrics_path=str(metrics_path),
    )

    assert result["ok"] is True
    assert result["feedback"]["status"] == "metric_missing"
    trajectory = TrajectoryStore(layout).show(quest_id="QFEED", trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["failure"]["class"] == "metric_missing"
    assert trajectory["result"]["status"] == "metric_invalid"


def test_feedback_ingest_blocks_on_protected_hash_mismatch(tmp_path: Path):
    from codex_scientist.services.feedback_ingest import FeedbackIngestService

    layout, trajectory_id = _setup(tmp_path)
    (tmp_path / "evaluate.py").write_text("print('tampered')\n", encoding="utf-8")
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"metrics": {"eval": {"mean_reward": 0.8}}}), encoding="utf-8")

    result = FeedbackIngestService(layout).ingest(
        quest_id="QFEED",
        env_id="env_toy",
        trajectory_id=trajectory_id,
        run_id="run_blocked",
        source_kind="local_metrics",
        metrics_path=str(metrics_path),
    )
    assert result["ok"] is False
    assert result["error_type"] == "protected_hash_mismatch"


def test_feedback_ingest_wandb_source_requires_revalidation(tmp_path: Path):
    from codex_scientist.services.feedback_ingest import FeedbackIngestService

    layout, trajectory_id = _setup(tmp_path)
    metrics_path = tmp_path / "wandb_metrics.json"
    metrics_path.write_text(json.dumps({"metrics": {"eval": {"mean_reward": 0.9}}}), encoding="utf-8")

    result = FeedbackIngestService(layout).ingest(
        quest_id="QFEED",
        env_id="env_toy",
        trajectory_id=trajectory_id,
        run_id="run_wandb",
        source_kind="wandb",
        metrics_path=str(metrics_path),
    )

    assert result["ok"] is True
    assert result["feedback"]["trusted_primary_metric"] is False
    assert result["feedback"]["requires_revalidation"] is True
    trajectory = TrajectoryStore(layout).show(quest_id="QFEED", trajectory_id=trajectory_id)["trajectory"]
    assert trajectory["result"]["status"] == "needs_revalidation"


def test_feedback_ingest_log_digest_redacts_token_like_strings(tmp_path: Path):
    from codex_scientist.services.feedback_ingest import FeedbackIngestService

    layout, trajectory_id = _setup(tmp_path)
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"metrics": {"eval": {"mean_reward": 0.8}}}), encoding="utf-8")
    log_path = tmp_path / "run.log"
    log_path.write_text("epoch ok\ntoken=supersecret\npassword=hunter2\n", encoding="utf-8")

    result = FeedbackIngestService(layout).ingest(
        quest_id="QFEED",
        env_id="env_toy",
        trajectory_id=trajectory_id,
        run_id="run_log",
        source_kind="local_metrics",
        metrics_path=str(metrics_path),
        log_paths=[str(log_path)],
        trusted_primary_metric=True,
    )

    rendered = str(result)
    assert result["ok"] is True
    assert "supersecret" not in rendered
    assert "hunter2" not in rendered
    assert "[REDACTED]" in rendered
