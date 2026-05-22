"""MCP request context helpers for CodexScientist."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codex_scientist.services.project_state import ProjectLayout, ProjectRootResolver


def _path_value(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text).expanduser().resolve() if text else None


def _text_value(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@dataclass(frozen=True)
class CodexScientistMcpContext:
    """Resolved MCP context for a Codex-managed root-bound research turn.

    The Codex project root is the storage identity. `quest_id` is provenance only;
    it never changes where durable state is read or written.
    """

    project_root: Path | None = None
    home: Path | None = None
    quest_id: str | None = None
    quest_root: Path | None = None
    run_id: str | None = None
    active_stage: str | None = None
    conversation_id: str | None = None
    worktree_root: Path | None = None

    @classmethod
    def from_env(cls, overrides: dict[str, Any] | None = None) -> "CodexScientistMcpContext":
        values = dict(overrides or {})
        env = os.environ
        resolver_args: dict[str, Any] = {}
        if "project" in values:
            resolver_args["project"] = values.get("project")
        elif "project_root" in values:
            resolver_args["project_root"] = values.get("project_root")
        elif env.get("CODEXSCIENTIST_PROJECT_ROOT"):
            resolver_args["project_root"] = env.get("CODEXSCIENTIST_PROJECT_ROOT")
        project_root = ProjectRootResolver.resolve(resolver_args)
        research_root = project_root / "CodexScientist"
        quest_id = _text_value(values.get("quest_id") or env.get("CS_QUEST_ID"))
        run_id = _text_value(values.get("run_id") or env.get("CS_RUN_ID"))
        active_stage = _text_value(values.get("active_stage") or values.get("stage") or env.get("CS_ACTIVE_STAGE"))
        conversation_id = _text_value(values.get("conversation_id") or values.get("session_id") or env.get("CS_CONVERSATION_ID"))
        worktree_root = _path_value(values.get("worktree_root") or env.get("CS_WORKTREE_ROOT"))
        return cls(
            project_root=project_root,
            home=research_root,
            quest_id=quest_id,
            quest_root=research_root,
            run_id=run_id,
            active_stage=active_stage,
            conversation_id=conversation_id,
            worktree_root=worktree_root,
        )

    def require_project_root(self) -> Path:
        return self.project_root or ProjectRootResolver.resolve({})

    def require_research_root(self) -> Path:
        return self.require_project_root() / "CodexScientist"

    def require_quest_root(self) -> Path:
        return self.require_research_root()

    def resolve_project_layout(self) -> ProjectLayout:
        return ProjectLayout.from_project_root(self.require_project_root())
