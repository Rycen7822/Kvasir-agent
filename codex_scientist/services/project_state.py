from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


QUEST_DIRS: tuple[str, ...] = (
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
)

QUEST_FILES: tuple[str, ...] = (
    "quest.yaml",
    "brief.md",
    "plan.md",
    "status.md",
    "summary.md",
    "events/events.jsonl",
)


def _safe_segment(value: str, *, label: str) -> str:
    segment = str(value or "").strip()
    if not segment or segment in {".", ".."} or "/" in segment or "\\" in segment:
        raise ValueError(f"Invalid {label}: {value!r}")
    return segment


@dataclass(frozen=True)
class QuestLayout:
    """Canonical quest-scoped paths under a project-local state root."""

    project_layout: "ProjectLayout"
    quest_id: str
    quest_root: Path

    @property
    def event_log_path(self) -> Path:
        return self.quest_root / "events" / "events.jsonl"

    @property
    def runtime_dir(self) -> Path:
        return self.quest_root / "runtime"

    @property
    def queue_dir(self) -> Path:
        return self.runtime_dir / "queue"

    @property
    def runs_dir(self) -> Path:
        return self.runtime_dir / "runs"

    @property
    def trials_dir(self) -> Path:
        return self.quest_root / "experiments" / "trials"

    def detail_path(self, relative_path: str | Path) -> Path:
        return self.project_layout.quest_detail_path(self.quest_id, relative_path)


@dataclass(frozen=True)
class ProjectLayout:
    """Canonical project-local paths for Codex-Scientist state."""

    project_root: Path

    @classmethod
    def from_project_root(cls, project_root: str | Path) -> "ProjectLayout":
        return cls(project_root=Path(project_root).expanduser().resolve())

    @property
    def state_root(self) -> Path:
        return self.project_root / "CodexScientist"

    @property
    def quests_dir(self) -> Path:
        return self.state_root / "quests"

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
        self.quests_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def quest_root_for(self, quest_id: str) -> Path:
        safe_id = _safe_segment(quest_id, label="quest_id")
        return self.quests_dir / safe_id

    def quest_layout(self, quest_id: str) -> QuestLayout:
        safe_id = _safe_segment(quest_id, label="quest_id")
        return QuestLayout(project_layout=self, quest_id=safe_id, quest_root=self.quests_dir / safe_id)

    def ensure_quest_layout(self, quest_id: str) -> QuestLayout:
        quest = self.quest_layout(quest_id)
        self.ensure_core_dirs()
        quest.quest_root.mkdir(parents=True, exist_ok=True)
        for relative_dir in QUEST_DIRS:
            (quest.quest_root / relative_dir).mkdir(parents=True, exist_ok=True)
        for relative_file in QUEST_FILES:
            path = quest.quest_root / relative_file
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("" if path.suffix != ".yaml" else "{}\n", encoding="utf-8")
        return quest

    def quest_detail_path(self, quest_id: str, relative_path: str | Path) -> Path:
        quest = self.quest_layout(quest_id)
        rel = Path(relative_path)
        if rel.is_absolute():
            raise ValueError(f"Quest detail path must be relative: {relative_path!r}")
        if any(part in {"", ".", ".."} for part in rel.parts):
            raise ValueError(f"Unsafe quest detail path: {relative_path!r}")
        target = (quest.quest_root / rel).resolve()
        root = quest.quest_root.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Quest detail path escapes quest root: {relative_path!r}") from exc
        return target

    def quest_queue_job_path(self, quest_id: str, job_id: str) -> Path:
        safe_job_id = _safe_segment(job_id, label="job_id")
        return self.quest_detail_path(quest_id, Path("runtime") / "queue" / f"{safe_job_id}.json")

    def quest_run_dir(self, quest_id: str, run_id: str) -> Path:
        safe_run_id = _safe_segment(run_id, label="run_id")
        return self.quest_detail_path(quest_id, Path("runtime") / "runs" / safe_run_id)

    def quest_trial_path(self, quest_id: str, trial_id: str) -> Path:
        safe_trial_id = _safe_segment(trial_id, label="trial_id")
        return self.quest_detail_path(quest_id, Path("experiments") / "trials" / safe_trial_id / "trial.json")
