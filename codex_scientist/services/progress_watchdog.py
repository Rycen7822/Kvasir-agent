from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .checkpoint import CheckpointService
from .event_store import EventStore
from .goal_loop import GoalLoopService
from .project_state import ProjectLayout
from .watchdog import WatchdogService


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _safe_int(value: Any, default: int, *, minimum: int = 0, maximum: int = 86400) -> int:
    try:
        return max(minimum, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


class ProgressWatchdogService:
    """Quest-local progress watchdog for Codex goal long-run recovery."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def state_path(self, quest_id: str) -> Path:
        quest = self.layout.ensure_quest_layout(quest_id)
        return quest.quest_root / "runtime" / "progress_watchdog.json"

    def runtime_checkpoint_dir(self, quest_id: str) -> Path:
        quest = self.layout.ensure_quest_layout(quest_id)
        return quest.quest_root / "runtime" / "checkpoints"

    def runtime_summary_path(self, quest_id: str) -> Path:
        quest = self.layout.ensure_quest_layout(quest_id)
        return quest.quest_root / "runtime" / "summary.md"

    def read_state(self, quest_id: str) -> dict[str, Any]:
        path = self.state_path(quest_id)
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
        latest = CheckpointService(self.layout).latest_checkpoint() or {}
        now = _utc_now()
        return {
            "schema_version": 1,
            "quest_id": quest_id,
            "initialized_at": _iso(now),
            "last_checkpoint_id": latest.get("checkpoint_id"),
            "last_checkpoint_at": latest.get("created_at") or _iso(now),
            "tool_calls_since_last_checkpoint": 0,
            "seconds_since_last_checkpoint": 0,
            "last_state_changing_tool": None,
            "last_user_visible_milestone": None,
            "pending_checkpoint_reason": None,
            "next_checkpoint_tool": "cs_checkpoint",
        }

    def _write_state(self, quest_id: str, state: dict[str, Any]) -> None:
        path = self.state_path(quest_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _milestone(tool_name: str, args: dict[str, Any], payload: dict[str, Any]) -> str:
        for key in ("message", "title", "phase", "next_action", "summary"):
            if args.get(key):
                return f"{tool_name}: {str(args[key])[:120]}"
        if payload.get("checkpoint_id"):
            return f"{tool_name}: {payload['checkpoint_id']}"
        return tool_name

    def record_state_changing_tool(self, *, quest_id: str, tool_name: str, args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        state = self.read_state(quest_id)
        now = _utc_now()
        last_checkpoint_at = _parse_iso(str(state.get("last_checkpoint_at") or "")) or now
        calls = int(state.get("tool_calls_since_last_checkpoint") or 0) + 1
        seconds = max(0, int((now - last_checkpoint_at).total_seconds()))
        tool_threshold = _safe_int(args.get("checkpoint_tool_threshold"), 5, minimum=1, maximum=1000)
        seconds_threshold = _safe_int(args.get("checkpoint_seconds_threshold"), 1800, minimum=1, maximum=604800)
        reason = None
        if calls >= tool_threshold:
            reason = "tool_call_threshold"
        elif seconds >= seconds_threshold:
            reason = "time_threshold"
        state.update(
            {
                "tool_calls_since_last_checkpoint": calls,
                "seconds_since_last_checkpoint": seconds,
                "last_state_changing_tool": tool_name,
                "last_user_visible_milestone": self._milestone(tool_name, args, payload),
                "pending_checkpoint_reason": reason,
                "next_checkpoint_tool": "cs_checkpoint",
                "updated_at": _iso(now),
            }
        )
        self._write_state(quest_id, state)
        return {
            "checkpoint_due": reason is not None,
            "checkpoint_reason": reason,
            "next_checkpoint_tool": "cs_checkpoint",
            "progress_watchdog": {
                "tool_calls_since_last_checkpoint": calls,
                "seconds_since_last_checkpoint": seconds,
                "last_state_changing_tool": tool_name,
                "last_user_visible_milestone": state.get("last_user_visible_milestone"),
                "pending_checkpoint_reason": reason,
                "state_path": str(self.state_path(quest_id)),
            },
        }

    def reset_after_checkpoint(self, *, quest_id: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        checkpoint_id = str(checkpoint.get("checkpoint_id") or (checkpoint.get("checkpoint") or {}).get("checkpoint_id") or "checkpoint")
        runtime_dir = self.runtime_checkpoint_dir(quest_id)
        runtime_dir.mkdir(parents=True, exist_ok=True)
        runtime_checkpoint_path = runtime_dir / f"{checkpoint_id}.md"
        runtime_summary_path = self.runtime_summary_path(quest_id)
        goal_state_path = GoalLoopService(self.layout).state_path(quest_id)
        goal_state = GoalLoopService(self.layout).read_state(quest_id)
        markdown = "\n".join(
            [
                f"# Runtime Checkpoint {checkpoint_id}",
                "",
                f"created_at: {checkpoint.get('checkpoint', checkpoint).get('created_at') or _iso(now)}",
                f"phase: {checkpoint.get('checkpoint', checkpoint).get('phase')}",
                f"next_action: {checkpoint.get('checkpoint', checkpoint).get('next_action')}",
                f"event_seq: {checkpoint.get('checkpoint', checkpoint).get('event_seq')}",
                "",
            ]
        )
        runtime_checkpoint_path.write_text(markdown, encoding="utf-8")
        runtime_summary_path.write_text(markdown, encoding="utf-8")
        if not goal_state_path.exists():
            goal_state_path.parent.mkdir(parents=True, exist_ok=True)
            goal_state_path.write_text(json.dumps(goal_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        state = self.read_state(quest_id)
        state.update(
            {
                "last_checkpoint_id": checkpoint_id,
                "last_checkpoint_at": checkpoint.get("checkpoint", checkpoint).get("created_at") or _iso(now),
                "tool_calls_since_last_checkpoint": 0,
                "seconds_since_last_checkpoint": 0,
                "pending_checkpoint_reason": None,
                "next_checkpoint_tool": "cs_checkpoint",
                "updated_at": _iso(now),
            }
        )
        self._write_state(quest_id, state)
        self.events.append("progress_watchdog.checkpoint_reset", {"quest_id": quest_id, "checkpoint_id": checkpoint_id})
        return {
            "checkpoint_due": False,
            "checkpoint_reason": None,
            "next_checkpoint_tool": "cs_checkpoint",
            "runtime_checkpoint_path": str(runtime_checkpoint_path),
            "runtime_summary_path": str(runtime_summary_path),
            "goal_state_path": str(goal_state_path),
            "progress_watchdog": {"state_path": str(self.state_path(quest_id)), "tool_calls_since_last_checkpoint": 0, "pending_checkpoint_reason": None},
        }

    def reconcile_goal_runtime(self, *, quest_id: str, timeout_seconds: int) -> dict[str, Any]:
        result = WatchdogService(self.layout).reconcile_stale_runs(timeout_seconds=timeout_seconds)
        stuck_runs = list(result.get("stuck_runs") or [])
        gate: dict[str, Any] | None = None
        if stuck_runs:
            run_id = str(stuck_runs[0])
            gate = {
                "stage": "experiment",
                "action_type": "crash_resume",
                "required_tool": "cs_log_digest",
                "required_inputs": ["quest_id", "run_id"],
                "blocking_reason": "runner_stuck",
                "run_id": run_id,
                "done_when": "inspect the redacted log digest, reconcile queue/runner state, then checkpoint",
            }
            GoalLoopService(self.layout).write_state(quest_id, active_stage="experiment", current_gate=gate)
        return {"ok": True, "quest_id": quest_id, "stuck_runs": stuck_runs, "current_gate": gate, "watchdog": result}
