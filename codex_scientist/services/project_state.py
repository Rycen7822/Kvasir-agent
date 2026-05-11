from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectLayout:
    """Canonical project-local paths for Codex-Scientist state."""

    project_root: Path

    @classmethod
    def from_project_root(cls, project_root: str | Path) -> "ProjectLayout":
        return cls(project_root=Path(project_root).expanduser().resolve())

    @property
    def state_root(self) -> Path:
        return self.project_root / "DeepScientist"

    @property
    def events_dir(self) -> Path:
        return self.state_root / "events"

    @property
    def runtime_dir(self) -> Path:
        return self.state_root / "runtime"

    @property
    def project_state_path(self) -> Path:
        return self.state_root / "project_state.json"

    @property
    def event_log_path(self) -> Path:
        return self.events_dir / "events.jsonl"

    def ensure_core_dirs(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
