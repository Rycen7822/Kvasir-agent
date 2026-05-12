from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_scientist.services.project_state import ProjectLayout


EXPECTED_QUEST_DIRS = {
    "events",
    "memory/decisions",
    "memory/episodes",
    "memory/ideas",
    "memory/knowledge",
    "memory/papers",
    "artifacts/approvals",
    "artifacts/baselines",
    "artifacts/decisions",
    "artifacts/graphs",
    "artifacts/ideas",
    "artifacts/milestones",
    "artifacts/progress",
    "artifacts/reports",
    "artifacts/runs",
    "baselines/imported",
    "baselines/local",
    "experiments/main",
    "experiments/analysis",
    "experiments/trials",
    "handoffs",
    "literature",
    "paper",
    "method_memory/negative",
    "method_memory/scoreboard",
    "method_memory/frontier",
    "runtime/bash_exec",
    "runtime/worktrees",
    "runtime/checkpoints",
    "runtime/runs",
    "runtime/queue",
    "tmp",
}

EXPECTED_QUEST_FILES = {"quest.yaml", "brief.md", "plan.md", "status.md", "summary.md", "events/events.jsonl"}


def test_project_layout_creates_quest_scoped_layout_and_rejects_escape(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    quest = layout.ensure_quest_layout("Q-001")

    assert quest.quest_root == tmp_path / "CodexScientist" / "quests" / "Q-001"
    assert quest.quest_root.is_dir()
    for rel in EXPECTED_QUEST_DIRS:
        assert (quest.quest_root / rel).is_dir(), rel
    for rel in EXPECTED_QUEST_FILES:
        assert (quest.quest_root / rel).exists(), rel

    assert layout.quest_detail_path("Q-001", "runtime/queue/job1.json") == quest.quest_root / "runtime" / "queue" / "job1.json"
    with pytest.raises(ValueError):
        layout.quest_detail_path("Q-001", "../escape.json")
    with pytest.raises(ValueError):
        layout.quest_root_for("../bad")


def test_legacy_global_queue_index_can_be_read_before_migration(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    legacy_state = {
        "schema_version": 1,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "jobs": {
            "legacy": {"job_id": "legacy", "command": "python old.py", "status": "pending", "attempts": 0, "run_ids": []}
        },
    }
    legacy_path = layout.state_root / "queue" / "queue_state.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(json.dumps(legacy_state), encoding="utf-8")

    from codex_scientist.services.queue import QueueService

    status = QueueService(layout).status()
    assert status["ok"] is True
    assert status["jobs"]["legacy"]["job_id"] == "legacy"
    assert "detail_path" not in status["jobs"]["legacy"]
