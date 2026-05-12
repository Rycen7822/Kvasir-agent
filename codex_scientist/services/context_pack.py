from __future__ import annotations

import hashlib
from pathlib import Path

from .event_store import EventStore
from .checkpoint import CheckpointService
from .frontier import FrontierService
from .journal import JournalService
from .goal_loop import GoalLoopService
from .manifest import ManifestService
from .project_state import ProjectLayout
from .queue import QueueService


class ContextPackService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.path = layout.state_root / "summaries" / "context_pack.md"

    @staticmethod
    def _line(value: object) -> str:
        text = str(value).replace("\n", " ")
        return text[:72]

    def _build_sections(self, quest_id: str | None = None) -> list[tuple[str, str]]:
        manifest = ManifestService(self.layout).read()
        queue = QueueService(self.layout).status()
        frontier = FrontierService(self.layout).select(limit=3)
        events = EventStore(self.layout).read_events()[-3:]
        latest_checkpoint = CheckpointService(self.layout).latest_checkpoint() or {}
        negative = JournalService(self.layout).list_negative_memory()[:3]

        project = manifest.get("project") if isinstance(manifest.get("project"), dict) else {}
        goal = manifest.get("goal") if isinstance(manifest.get("goal"), dict) else {}
        budgets = manifest.get("budgets") if isinstance(manifest.get("budgets"), dict) else {}
        context = budgets.get("context") if isinstance(budgets.get("context"), dict) else {}

        active_state = f"project={self._line(project.get('name', 'unknown'))}; goal={self._line(goal.get('title', 'unset'))}; phase={self._line(latest_checkpoint.get('phase', 'unset'))}"
        last_checkpoint = (
            f"id={self._line(latest_checkpoint.get('checkpoint_id', 'none'))}; "
            f"event_seq={self._line(latest_checkpoint.get('event_seq', 'none'))}; "
            f"next={self._line(latest_checkpoint.get('next_action', 'unset'))}"
        )
        next_action = self._line(latest_checkpoint.get("next_action") or "inspect gates and choose one bounded next action")
        metric_frontier = ",".join(item.get("idea_id", "?") for item in frontier) or "none"
        recent_events = ",".join(event.get("event_type", "?") for event in events) or "none"
        negative_line = ",".join(item.get("idea_id", "?") for item in negative) or "none"
        artifact_index = "paths+sha256 only; no inline large artifacts"
        log_digest = "bounded tails only"
        budget_state = f"max_context={context.get('max_context_pack_chars', 'unset')}; jobs={len(queue.get('jobs', {}))}"
        goal_loop_state = "none"
        if quest_id:
            state = GoalLoopService(self.layout).read_state(quest_id)
            goal_loop_state = (
                f"quest_id={self._line(state.get('quest_id', quest_id))}; "
                f"active_stage={self._line(state.get('active_stage', 'unset'))}; "
                f"gate={self._line((state.get('current_gate') or {}).get('required_tool', 'unset'))}; "
                f"next={self._line((state.get('next_action') or {}).get('required_tool', 'unset'))}"
            )

        return [
            ("active_state", active_state),
            ("last_checkpoint", last_checkpoint),
            ("goal_loop_state", goal_loop_state),
            ("next_action", next_action),
            ("metric_frontier", metric_frontier),
            ("recent_events", recent_events),
            ("relevant_negative_memory", negative_line),
            ("artifact_index", artifact_index),
            ("log_digest", log_digest),
            ("budget_state", budget_state),
        ]

    def render(self, *, max_chars: int, quest_id: str | None = None) -> str:
        sections = self._build_sections(quest_id=quest_id)
        content = "# Codex-Scientist Context Pack\n" + "\n".join(
            f"\n## {name}\n{body}" for name, body in sections
        ) + "\n"
        if len(content) <= max_chars:
            return content
        # Preserve required section headers. Trim bodies first; if the caller sets
        # an unrealistically low limit, still return a structurally valid compact
        # pack rather than dropping sections unpredictably.
        compact = "# Codex-Scientist Context Pack\n" + "\n".join(
            f"\n## {name}\n-" for name, _body in sections
        ) + "\n"
        return compact if len(compact) <= max_chars else compact[:max_chars]

    def write_context_pack(self, *, max_chars: int, quest_id: str | None = None) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = self.render(max_chars=max_chars, quest_id=quest_id)
        self.path.write_text(content, encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {"ok": True, "path": str(self.path), "content": content, "chars": len(content), "sha256": digest}
