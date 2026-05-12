"""MCP request context helpers for CodexScientist."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codex_scientist.services.project_state import ProjectLayout


def _path_value(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text).expanduser().resolve() if text else None


def _text_value(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@dataclass(frozen=True)
class CodexScientistMcpContext:
    """Resolved MCP context for a Codex-managed research turn.

    The context is intentionally small: it reads environment/request values and
    returns ProjectLayout paths. It does not execute commands or mutate state.
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
        project_root = _path_value(values.get("project") or values.get("project_root") or env.get("CODEXSCIENTIST_PROJECT_ROOT"))
        quest_id = _text_value(values.get("quest_id") or env.get("CS_QUEST_ID"))
        home = _path_value(values.get("home") or values.get("cs_home") or env.get("CS_HOME"))
        quest_root = _path_value(values.get("quest_root") or env.get("CS_QUEST_ROOT"))
        run_id = _text_value(values.get("run_id") or env.get("CS_RUN_ID"))
        active_stage = _text_value(values.get("active_stage") or values.get("stage") or env.get("CS_ACTIVE_STAGE"))
        conversation_id = _text_value(values.get("conversation_id") or values.get("session_id") or env.get("CS_CONVERSATION_ID"))
        worktree_root = _path_value(values.get("worktree_root") or env.get("CS_WORKTREE_ROOT"))
        return cls(
            project_root=project_root,
            home=home,
            quest_id=quest_id,
            quest_root=quest_root,
            run_id=run_id,
            active_stage=active_stage,
            conversation_id=conversation_id,
            worktree_root=worktree_root,
        )

    def require_project_root(self) -> Path:
        return self.project_root or Path.cwd().resolve()

    def require_quest_root(self) -> Path:
        if self.quest_root is not None:
            return self.quest_root
        if not self.quest_id:
            raise ValueError("quest_id or CS_QUEST_ROOT is required")
        return self.require_project_root() / "CodexScientist" / "quests" / self.quest_id

    def resolve_project_layout(self) -> ProjectLayout:
        return ProjectLayout.from_project_root(self.require_project_root())
