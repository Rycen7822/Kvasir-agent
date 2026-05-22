from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .checkpoint import CheckpointService
from .event_store import EventStore
from .manifest import ManifestService
from .project_state import ProjectLayout
from .queue import QueueService
from .runner import RunnerService


class ResumeService:
    """Build compact recovery views from project-local state."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.checkpoints = CheckpointService(layout)

    @staticmethod
    def _goal_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
        goal = manifest.get("goal") if isinstance(manifest.get("goal"), dict) else {}
        goal = goal if isinstance(goal, dict) else {}
        return {
            "title": str(goal.get("title") or ""),
            "success_criteria": list(goal.get("success_criteria") or []),
            "non_goals": list(goal.get("non_goals") or []),
        }

    def _goal_from_quest(self, quest_id: str | None) -> dict[str, Any]:
        return {"title": "", "success_criteria": [], "non_goals": []}

    @staticmethod
    def _goal_title_from_brief(path: Path) -> str:
        if not path.exists():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        in_goal = False
        for line in lines:
            text = line.strip()
            if text.lower() == "## goal":
                in_goal = True
                continue
            if in_goal:
                if text.startswith("## "):
                    break
                if text:
                    return text.lstrip("- ").strip()
        for line in lines:
            text = line.strip().lstrip("#").strip()
            if text and text.lower() not in {"quest brief", "goal", "initial notes"}:
                return text
        return ""

    @staticmethod
    def _autonomy_mode(manifest: dict[str, Any]) -> str:
        autonomy = manifest.get("autonomy") if isinstance(manifest.get("autonomy"), dict) else {}
        return str(autonomy.get("mode") or "copilot")

    @staticmethod
    def _active_job_id(queue_status: dict[str, Any]) -> str | None:
        for job_id, job in (queue_status.get("jobs") or {}).items():
            if isinstance(job, dict) and job.get("status") in {"running", "leased", "pending", "reconcile_required"}:
                return str(job_id)
        return None

    @staticmethod
    def _active_run_id(runs: list[dict[str, Any]]) -> str | None:
        for run in reversed(runs):
            if run.get("status") in {"running", "leased", "pending", "stuck"}:
                return str(run.get("run_id"))
        return None

    def resume_brief(
        self,
        *,
        max_chars: int = 8000,
        include_recent_events: int = 5,
        include_risks: bool = True,
        quest_id: str | None = None,
    ) -> dict[str, Any]:
        manifest = ManifestService(self.layout).read()
        latest = self.checkpoints.latest_checkpoint() or {}
        queue_status = QueueService(self.layout).status()
        runs = RunnerService(self.layout).list_runs()
        events = self.events.read_events()[-max(0, int(include_recent_events)):]
        goal = self._goal_from_manifest(manifest)
        if not goal.get("title") and quest_id:
            goal = self._goal_from_quest(quest_id)
        warnings: list[str] = []
        blocked_reason = None
        if not goal.get("title"):
            blocked_reason = "blocked_missing_goal"
            warnings.append("blocked_missing_goal")
        if int(max_chars) < 1000:
            warnings.append("budget_too_small")

        risk_flags = list(latest.get("risk_flags") or []) if include_risks else []
        active_run_id = self._active_run_id(runs)
        blocked_reason = str(blocked_reason or "").strip() or None
        brief = {
            "ok": True,
            "goal": goal,
            "current_quest": quest_id,
            "stage_label": None,
            "last_completed_action": latest.get("completed", [None])[-1] if isinstance(latest.get("completed"), list) and latest.get("completed") else None,
            "blocker": blocked_reason,
            "autonomy_mode": self._autonomy_mode(manifest),
            "active_phase": latest.get("phase"),
            "active_trial_id": None,
            "active_job_id": self._active_job_id(queue_status),
            "active_run_id": active_run_id,
            "last_checkpoint": latest or None,
            "recovery_anchor": str(latest.get("next_action") or "manual review of latest checkpoint and evidence gaps"),
            "blocked_reason": blocked_reason,
            "validation_status": list(latest.get("validation") or []),
            "budget_status": {
                "max_chars": int(max_chars),
                "queue_jobs": len(queue_status.get("jobs") or {}),
                "runs": len(runs),
            },
            "artifact_refs": list(latest.get("artifact_refs") or []),
            "risk_flags": risk_flags,
            "recent_events": [
                {"event_seq": event.get("event_seq"), "event_type": event.get("event_type")}
                for event in events
            ],
            "source_refs": [
                {"path": str(self.layout.state_root), "kind": "state_root"},
                {"path": str(self.checkpoints.latest_path), "kind": "latest_checkpoint"},
                {"path": str(self.layout.event_log_path), "kind": "event_log"},
                {"path": str(self.layout.state_root / "runtime" / "goal_state.json"), "kind": "goal_state"},
            ],
            "warnings": warnings,
        }
        brief["chars"] = len(json.dumps(brief, ensure_ascii=False, sort_keys=True, default=str))
        return brief

    def _seq_from_checkpoint(self, checkpoint_id: str | None) -> int | None:
        if not checkpoint_id:
            return None
        checkpoint = self.checkpoints.find_checkpoint(checkpoint_id)
        if checkpoint is None:
            return None
        return int(checkpoint.get("event_seq") or 0)

    def pack_delta(
        self,
        *,
        since_event_seq: int | None = None,
        since_checkpoint_id: str | None = None,
        max_chars: int = 6000,
    ) -> dict[str, Any]:
        base_seq = since_event_seq if since_event_seq is not None else self._seq_from_checkpoint(since_checkpoint_id)
        if since_checkpoint_id and base_seq is None:
            return {
                "ok": False,
                "error": f"Unknown checkpoint: {since_checkpoint_id}",
                "error_type": "unknown_checkpoint",
                "recoverable": True,
            }
        events = self.events.read_events_since(base_seq)
        changed_jobs: list[str] = []
        changed_runs: list[str] = []
        changed_artifacts: list[Any] = []
        changed_risks: list[str] = []
        for event in events:
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if payload.get("job_id") and str(payload.get("job_id")) not in changed_jobs:
                changed_jobs.append(str(payload.get("job_id")))
            if payload.get("run_id") and str(payload.get("run_id")) not in changed_runs:
                changed_runs.append(str(payload.get("run_id")))
            for key in ("artifact_refs", "artifacts"):
                for item in payload.get(key) or []:
                    if item not in changed_artifacts:
                        changed_artifacts.append(item)
            for item in payload.get("risk_flags") or []:
                text = str(item)
                if text not in changed_risks:
                    changed_risks.append(text)
        event_seqs = [int(event.get("event_seq") or 0) for event in events]
        delta = {
            "ok": True,
            "new_events_summary": [
                {"event_seq": event.get("event_seq"), "event_type": event.get("event_type")}
                for event in events
            ],
            "changed_trials": [],
            "changed_jobs": changed_jobs,
            "changed_runs": changed_runs,
            "changed_artifacts": changed_artifacts,
            "changed_risks": changed_risks,
            "next_recommended_call": {"tool": "cs_resume_brief", "reason": "refresh stable recovery anchors after reading delta"},
            "source_event_range": {
                "since_event_seq": since_event_seq,
                "since_checkpoint_id": since_checkpoint_id,
                "start_event_seq": min(event_seqs) if event_seqs else None,
                "end_event_seq": max(event_seqs) if event_seqs else int(base_seq or 0),
            },
            "source_refs": [{"path": str(self.layout.event_log_path), "kind": "event_log"}],
            "warnings": ["budget_too_small"] if int(max_chars) < 1000 else [],
        }
        delta["chars"] = len(json.dumps(delta, ensure_ascii=False, sort_keys=True, default=str))
        return delta
