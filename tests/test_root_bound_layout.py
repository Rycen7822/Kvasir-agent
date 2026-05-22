from __future__ import annotations

from pathlib import Path

import pytest

from codex_scientist.services.project_state import ProjectLayout, ResearchLayout


def test_research_layout_creates_root_bound_dirs_without_legacy_quests(tmp_path: Path) -> None:
    layout = ProjectLayout.from_project_root(tmp_path)

    research = layout.ensure_research_layout()

    assert isinstance(research, ResearchLayout)
    assert research.project_root == tmp_path.resolve()
    assert research.state_root == tmp_path / "CodexScientist"
    assert research.manifest_path == research.state_root / "research.yaml"
    assert research.event_log_path == research.state_root / "events" / "events.jsonl"
    for relative_dir in [
        "events",
        "memory/decisions",
        "memory/episodes",
        "memory/ideas",
        "memory/knowledge",
        "memory/papers",
        "memory/templates",
        "artifacts/runs",
        "artifacts/execution_grounded",
        "baselines/local",
        "experiments/main",
        "environments",
        "trajectories",
        "variants",
        "method_memory/negative",
        "runtime/queue",
        "runtime/execution_grounded",
        "queue",
        "runs",
        "trials",
        "summaries",
        "paper",
        "handoffs",
        "migrations",
        "tmp",
    ]:
        assert (research.state_root / relative_dir).is_dir(), relative_dir
    assert not (research.state_root / "quests").exists()
    assert not research.manifest_path.exists()


def test_research_layout_safe_paths_reject_escape_and_absolute_paths(tmp_path: Path) -> None:
    research = ProjectLayout.from_project_root(tmp_path).research

    assert research.state_path("memory/ideas/item.md") == (tmp_path / "CodexScientist" / "memory" / "ideas" / "item.md").resolve()
    assert research.root_detail_path("experiments/run.py") == (tmp_path / "experiments" / "run.py").resolve()

    for bad in ["", ".", "..", "../escape", "memory//bad", Path("/tmp/outside")]:
        with pytest.raises(ValueError):
            research.state_path(bad)
        with pytest.raises(ValueError):
            research.root_detail_path(bad)


def test_project_layout_keeps_legacy_quest_api_explicitly_legacy(tmp_path: Path) -> None:
    layout = ProjectLayout.from_project_root(tmp_path)

    assert layout.legacy_quests_dir == tmp_path / "CodexScientist" / "quests"
    assert layout.legacy_quest_root_for("Q1") == layout.legacy_quests_dir / "Q1"
    legacy = layout.ensure_legacy_quest_layout("Q1")

    assert legacy.quest_root == layout.legacy_quests_dir / "Q1"
    assert (legacy.quest_root / "quest.yaml").exists()
