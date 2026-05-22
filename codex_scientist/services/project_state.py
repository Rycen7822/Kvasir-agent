from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESEARCH_DIRS: tuple[str, ...] = (
    "events",
    "memory/decisions",
    "memory/episodes",
    "memory/ideas",
    "memory/knowledge",
    "memory/papers",
    "memory/templates",
    "artifacts/approvals",
    "artifacts/baselines",
    "artifacts/decisions",
    "artifacts/graphs",
    "artifacts/ideas",
    "artifacts/milestones",
    "artifacts/progress",
    "artifacts/reports",
    "artifacts/runs",
    "artifacts/execution_grounded",
    "baselines/imported",
    "baselines/local",
    "experiments/main",
    "experiments/analysis",
    "experiments/trials",
    "environments",
    "trajectories",
    "variants",
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
    "runtime/execution_grounded",
    "runtime/execution_grounded/evolutionary_rounds",
    "queue",
    "runs",
    "trials",
    "summaries",
    "migrations",
    "tmp",
)

QUEST_DIRS: tuple[str, ...] = RESEARCH_DIRS

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


def _safe_relative_path(value: str | Path, *, label: str) -> Path:
    raw = str(value)
    rel = Path(value)
    if not raw.strip() or raw.strip() in {".", ".."} or rel.is_absolute() or "//" in raw or "\\" in raw:
        raise ValueError(f"Unsafe {label}: {value!r}")
    if any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError(f"Unsafe {label}: {value!r}")
    return rel


class ProjectRootResolver:
    """Resolve the Codex project root without consulting quest/session state."""

    @staticmethod
    def resolve(args: dict[str, Any] | None = None) -> Path:
        raw_args = args or {}
        if "project" in raw_args:
            return ProjectRootResolver._explicit_path(raw_args.get("project"), label="project")
        if "project_root" in raw_args:
            return ProjectRootResolver._explicit_path(raw_args.get("project_root"), label="project_root")
        env_root = os.environ.get("CODEXSCIENTIST_PROJECT_ROOT")
        if env_root:
            return ProjectRootResolver._explicit_path(env_root, label="CODEXSCIENTIST_PROJECT_ROOT")
        cwd = Path.cwd().resolve()
        manifest_parent = ProjectRootResolver._nearest_parent_with(cwd, Path("CodexScientist") / "research.yaml")
        if manifest_parent is not None:
            return manifest_parent
        git_parent = ProjectRootResolver._nearest_parent_with(cwd, Path(".git"))
        if git_parent is not None:
            return git_parent
        return cwd

    @staticmethod
    def _explicit_path(value: Any, *, label: str) -> Path:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError(f"Invalid {label}: empty path")
        path = Path(raw).expanduser()
        if ".." in path.parts:
            raise ValueError(f"Invalid {label}: path traversal is not allowed")
        return path.resolve()

    @staticmethod
    def _nearest_parent_with(start: Path, relative: Path) -> Path | None:
        for parent in (start, *start.parents):
            if (parent / relative).exists():
                return parent.resolve()
        return None


@dataclass(frozen=True)
class ResearchLayout:
    project_root: Path

    @property
    def state_root(self) -> Path:
        return self.project_root / "CodexScientist"

    @property
    def manifest_path(self) -> Path:
        return self.state_root / "research.yaml"

    @property
    def events_dir(self) -> Path:
        return self.state_root / "events"

    @property
    def event_log_path(self) -> Path:
        return self.events_dir / "events.jsonl"

    @property
    def memory_dir(self) -> Path:
        return self.state_root / "memory"

    @property
    def artifacts_dir(self) -> Path:
        return self.state_root / "artifacts"

    @property
    def baselines_dir(self) -> Path:
        return self.state_root / "baselines"

    @property
    def experiments_dir(self) -> Path:
        return self.state_root / "experiments"

    @property
    def method_memory_dir(self) -> Path:
        return self.state_root / "method_memory"

    @property
    def runtime_dir(self) -> Path:
        return self.state_root / "runtime"

    @property
    def queue_dir(self) -> Path:
        return self.state_root / "queue"

    @property
    def runs_dir(self) -> Path:
        return self.state_root / "runs"

    @property
    def trials_dir(self) -> Path:
        return self.state_root / "trials"

    @property
    def summaries_dir(self) -> Path:
        return self.state_root / "summaries"

    def ensure_core_dirs(self) -> None:
        for relative_dir in RESEARCH_DIRS:
            (self.state_root / relative_dir).mkdir(parents=True, exist_ok=True)

    def state_path(self, relative_path: str | Path) -> Path:
        rel = _safe_relative_path(relative_path, label="state path")
        target = (self.state_root / rel).resolve()
        root = self.state_root.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"State path escapes research state root: {relative_path!r}") from exc
        return target

    def root_detail_path(self, relative_path: str | Path) -> Path:
        rel = _safe_relative_path(relative_path, label="project detail path")
        target = (self.project_root / rel).resolve()
        root = self.project_root.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Project detail path escapes project root: {relative_path!r}") from exc
        return target


@dataclass(frozen=True)
class QuestLayout:
    """Legacy quest-scoped paths under a project-local state root."""

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
        return self.project_layout.legacy_quest_detail_path(self.quest_id, relative_path)


@dataclass(frozen=True)
class ProjectLayout:
    """Canonical project-local paths for Codex-Scientist state."""

    project_root: Path

    @classmethod
    def from_project_root(cls, project_root: str | Path) -> "ProjectLayout":
        return cls(project_root=Path(project_root).expanduser().resolve())

    @property
    def research(self) -> ResearchLayout:
        return ResearchLayout(self.project_root)

    @property
    def state_root(self) -> Path:
        return self.research.state_root

    @property
    def legacy_quests_dir(self) -> Path:
        return self.state_root / "quests"

    @property
    def quests_dir(self) -> Path:
        return self.legacy_quests_dir

    @property
    def events_dir(self) -> Path:
        return self.research.events_dir

    @property
    def runtime_dir(self) -> Path:
        return self.research.runtime_dir

    @property
    def project_state_path(self) -> Path:
        return self.state_root / "project_state.json"

    @property
    def event_log_path(self) -> Path:
        return self.research.event_log_path

    def ensure_core_dirs(self) -> None:
        self.ensure_research_layout()

    def ensure_research_layout(self) -> ResearchLayout:
        research = self.research
        research.ensure_core_dirs()
        return research

    def legacy_quest_root_for(self, quest_id: str) -> Path:
        safe_id = _safe_segment(quest_id, label="quest_id")
        return self.legacy_quests_dir / safe_id

    def quest_root_for(self, quest_id: str) -> Path:
        return self.legacy_quest_root_for(quest_id)

    def legacy_quest_layout(self, quest_id: str) -> QuestLayout:
        safe_id = _safe_segment(quest_id, label="quest_id")
        return QuestLayout(project_layout=self, quest_id=safe_id, quest_root=self.legacy_quests_dir / safe_id)

    def quest_layout(self, quest_id: str) -> QuestLayout:
        return self.legacy_quest_layout(quest_id)

    def ensure_legacy_quest_layout(self, quest_id: str) -> QuestLayout:
        quest = self.legacy_quest_layout(quest_id)
        self.ensure_research_layout()
        quest.quest_root.mkdir(parents=True, exist_ok=True)
        for relative_dir in QUEST_DIRS:
            (quest.quest_root / relative_dir).mkdir(parents=True, exist_ok=True)
        for relative_file in QUEST_FILES:
            path = quest.quest_root / relative_file
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("" if path.suffix != ".yaml" else "{}\n", encoding="utf-8")
        return quest

    def ensure_quest_layout(self, quest_id: str) -> QuestLayout:
        return self.ensure_legacy_quest_layout(quest_id)

    def legacy_quest_detail_path(self, quest_id: str, relative_path: str | Path) -> Path:
        quest = self.legacy_quest_layout(quest_id)
        rel = _safe_relative_path(relative_path, label="legacy quest detail path")
        target = (quest.quest_root / rel).resolve()
        root = quest.quest_root.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Quest detail path escapes quest root: {relative_path!r}") from exc
        return target

    def quest_detail_path(self, quest_id: str, relative_path: str | Path) -> Path:
        return self.legacy_quest_detail_path(quest_id, relative_path)

    def quest_queue_job_path(self, quest_id: str, job_id: str) -> Path:
        safe_job_id = _safe_segment(job_id, label="job_id")
        return self.legacy_quest_detail_path(quest_id, Path("runtime") / "queue" / f"{safe_job_id}.json")

    def quest_run_dir(self, quest_id: str, run_id: str) -> Path:
        safe_run_id = _safe_segment(run_id, label="run_id")
        return self.legacy_quest_detail_path(quest_id, Path("runtime") / "runs" / safe_run_id)

    def quest_trial_path(self, quest_id: str, trial_id: str) -> Path:
        safe_trial_id = _safe_segment(trial_id, label="trial_id")
        return self.legacy_quest_detail_path(quest_id, Path("experiments") / "trials" / safe_trial_id / "trial.json")
