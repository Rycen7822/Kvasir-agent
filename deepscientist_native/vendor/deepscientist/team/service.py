from __future__ import annotations

from pathlib import Path

from ..shared import ensure_dir


class SingleTeamService:
    def __init__(self, home: Path) -> None:
        self.home = home

    def snapshot(self, quest_root: Path) -> dict:
        worktrees_root = ensure_dir(quest_root / ".ds" / "worktrees")
        active_workers = []
        for path in sorted(worktrees_root.iterdir()):
            if path.is_dir():
                active_workers.append({"worker_id": path.name, "worktree_root": str(path)})
        return {
            "mode": "single" if not active_workers else "lead-worker",
            "active_workers": active_workers,
        }

    def prepare_worktree_root(self, quest_root: Path, run_id: str) -> Path:
        return ensure_dir(quest_root / ".ds" / "worktrees" / run_id)
