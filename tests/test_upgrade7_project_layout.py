from __future__ import annotations

from pathlib import Path

from codex_scientist.services.project_state import ProjectLayout


def test_execution_grounded_dirs_created(tmp_path: Path):
    quest = ProjectLayout.from_project_root(tmp_path).ensure_quest_layout("QEG")
    for rel in [
        "environments",
        "trajectories",
        "variants",
        "artifacts/execution_grounded",
        "runtime/execution_grounded",
        "runtime/execution_grounded/evolutionary_rounds",
        "runtime/worktrees",
    ]:
        assert (quest.quest_root / rel).is_dir(), rel
