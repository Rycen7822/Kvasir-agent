from __future__ import annotations

from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.project_state import ProjectLayout

from test_upgrade7_environment_service import _valid_manifest


def _register_env(tmp_path: Path, *, direction: str = "maximize", value: float = 0.5, env_id: str = "env_toy") -> ProjectLayout:
    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _valid_manifest(tmp_path, quest_id="QTRAJ")
    manifest["env_id"] = env_id
    manifest["baseline"]["baseline_metric"]["direction"] = direction
    manifest["baseline"]["baseline_metric"]["value"] = value
    manifest["primary_metric"]["direction"] = direction
    assert EnvironmentService(layout).register(quest_id="QTRAJ", manifest=manifest)["ok"] is True
    return layout


def _idea(idea_id: str = "idea_1") -> dict:
    return {"idea_id": idea_id, "title": "Idea", "hypothesis": "Improve metric", "mechanism": "small change", "implementation_plan": "edit train.py"}


def test_trajectory_create_show_round_trip(tmp_path: Path):
    from codex_scientist.services.trajectory import TrajectoryStore

    layout = _register_env(tmp_path)
    store = TrajectoryStore(layout)

    created = store.create(quest_id="QTRAJ", env_id="env_toy", idea=_idea(), parents=["traj_parent"], strategy="manual")
    assert created["ok"] is True
    assert created["trajectory_id"].startswith("traj_")

    shown = store.show(quest_id="QTRAJ", trajectory_id=created["trajectory_id"])
    assert shown["ok"] is True
    trajectory = shown["trajectory"]
    assert trajectory["idea"]["idea_id"] == "idea_1"
    assert trajectory["result"]["status"] == "pending"
    assert trajectory["lineage"]["parent_trajectory_ids"] == ["traj_parent"]


def test_trajectory_update_result_with_metric_invalid_failure(tmp_path: Path):
    from codex_scientist.services.trajectory import TrajectoryStore

    layout = _register_env(tmp_path)
    store = TrajectoryStore(layout)
    trajectory_id = store.create(quest_id="QTRAJ", env_id="env_toy", idea=_idea())["trajectory_id"]

    updated = store.update_result(
        quest_id="QTRAJ",
        trajectory_id=trajectory_id,
        result={"status": "metric_invalid", "primary_metric": None},
        failure={"class": "metric_invalid", "message": "missing primary metric"},
    )
    assert updated["ok"] is True

    shown = store.show(quest_id="QTRAJ", trajectory_id=trajectory_id)["trajectory"]
    assert shown["result"]["status"] == "metric_invalid"
    assert shown["failure"]["class"] == "metric_invalid"

    bad = store.update_result(quest_id="QTRAJ", trajectory_id=trajectory_id, result={}, failure={"class": "not_a_failure"})
    assert bad["ok"] is False
    assert bad["error_type"] == "invalid_failure_class"


def test_trajectory_positive_search_respects_metric_direction(tmp_path: Path):
    from codex_scientist.services.trajectory import TrajectoryStore

    layout = _register_env(tmp_path, direction="maximize", value=0.5)
    store = TrajectoryStore(layout)
    good_id = store.create(quest_id="QTRAJ", env_id="env_toy", idea=_idea("idea_good"))["trajectory_id"]
    bad_id = store.create(quest_id="QTRAJ", env_id="env_toy", idea=_idea("idea_bad"))["trajectory_id"]

    store.update_result(
        quest_id="QTRAJ",
        trajectory_id=good_id,
        result={"status": "evaluated", "primary_metric": {"name": "eval/mean_reward", "value": 0.6, "direction": "maximize"}, "trusted_primary_metric": True},
    )
    store.update_result(
        quest_id="QTRAJ",
        trajectory_id=bad_id,
        result={"status": "evaluated", "primary_metric": {"name": "eval/mean_reward", "value": 0.4, "direction": "maximize"}, "trusted_primary_metric": True},
    )

    result = store.search(quest_id="QTRAJ", env_id="env_toy", positive_only=True)
    assert result["ok"] is True
    assert [item["trajectory_id"] for item in result["trajectories"]] == [good_id]


def test_trajectory_show_rejects_path_escape(tmp_path: Path):
    from codex_scientist.services.trajectory import TrajectoryStore

    store = TrajectoryStore(ProjectLayout.from_project_root(tmp_path))
    result = store.show(quest_id="QTRAJ", trajectory_id="../escape")
    assert result["ok"] is False
    assert result["error_type"] == "invalid_path"
