from __future__ import annotations

import math
from typing import Any

from .environment import EnvironmentService
from .event_store import EventStore
from .method_improvement import MethodImprovementService
from .project_state import ProjectLayout
from .trajectory import TrajectoryStore


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


class ExecutionHooksService:
    """Safe service-level hooks for execution-grounded feedback.

    Hooks are intentionally fail-soft callers' side effects: they write events/derived state but must not be the authority for claims or hide the primary execution result.
    """

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def on_feedback_ingested(self, *, quest_id: str, env_id: str, trajectory_id: str, feedback: dict[str, Any], feedback_path: str) -> dict[str, Any]:
        store = TrajectoryStore(self.layout)
        shown = store.show(quest_id=quest_id, trajectory_id=trajectory_id)
        if shown.get("ok") is not True:
            return shown
        trajectory = shown["trajectory"]
        trusted = feedback.get("trusted_primary_metric") is True
        if not trusted:
            updated = store.update_claimability(
                quest_id=quest_id,
                trajectory_id=trajectory_id,
                claimability={
                    "claim_gate_status": "needs_revalidation",
                    "blocking_reasons": ["metric_untrusted"],
                    "source": "feedback_hook",
                    "feedback_path": feedback_path,
                },
            )
            self.events.append(
                "hook.feedback_ingested",
                {"quest_id": quest_id, "env_id": env_id, "trajectory_id": trajectory_id, "status": "needs_revalidation"},
                idempotency_key=f"hook.feedback_ingested:{quest_id}:{trajectory_id}:{feedback.get('run_id')}:untrusted",
            )
            return {"ok": True, "hook": "feedback_ingested", "claimability": updated, "scoreboard_updated": False}

        raw_metric = feedback.get("primary_metric")
        metric = raw_metric if isinstance(raw_metric, dict) else {}
        current = _float_or_none(metric.get("value"))
        env_payload = EnvironmentService(self.layout).show(quest_id=quest_id, env_id=env_id)
        raw_environment = env_payload.get("environment") if env_payload.get("ok") is True else None
        environment = raw_environment if isinstance(raw_environment, dict) else {}
        raw_baseline = environment.get("baseline")
        baseline_section = raw_baseline if isinstance(raw_baseline, dict) else {}
        raw_baseline_metric = baseline_section.get("baseline_metric")
        baseline = raw_baseline_metric if isinstance(raw_baseline_metric, dict) else {}
        baseline_value = _float_or_none(baseline.get("value"))
        direction = str(metric.get("direction") or baseline.get("direction") or "maximize")
        invalid_reasons: list[str] = []
        if str(feedback.get("status") or "") != "parsed":
            invalid_reasons.append(str(feedback.get("status") or "metric_invalid"))
        if current is None:
            invalid_reasons.append("metric_invalid")
        if baseline_value is None:
            invalid_reasons.append("baseline_missing")
        if invalid_reasons:
            blocking_reasons = sorted(set(reason for reason in invalid_reasons if reason))
            updated = store.update_claimability(
                quest_id=quest_id,
                trajectory_id=trajectory_id,
                claimability={
                    "claim_gate_status": "needs_revalidation",
                    "blocking_reasons": blocking_reasons,
                    "source": "feedback_hook",
                    "feedback_path": feedback_path,
                },
            )
            self.events.append(
                "hook.feedback_ingested",
                {"quest_id": quest_id, "env_id": env_id, "trajectory_id": trajectory_id, "status": "needs_revalidation", "blocking_reasons": blocking_reasons},
                idempotency_key=f"hook.feedback_ingested:{quest_id}:{trajectory_id}:{feedback.get('run_id')}:invalid",
            )
            return {"ok": True, "hook": "feedback_ingested", "claimability": updated, "scoreboard_updated": False}
        assert current is not None
        assert baseline_value is not None
        delta = baseline_value - current if direction == "minimize" else current - baseline_value
        outcome = "positive" if delta > 0 else "negative"
        idea = trajectory.get("idea") if isinstance(trajectory.get("idea"), dict) else {}
        lineage = trajectory.get("lineage") if isinstance(trajectory.get("lineage"), dict) else {}
        idea_id = str(idea.get("idea_id") or trajectory_id)
        mechanism = str(idea.get("mechanism_family") or lineage.get("mechanism_family") or "")
        scoreboard = MethodImprovementService(self.layout).update_scoreboard(
            quest_id=quest_id,
            idea_id=idea_id,
            outcome=outcome,
            metric_delta=delta,
            lesson=f"execution feedback {feedback.get('run_id')}",
            mechanism=mechanism,
        )
        claimability = {
            "claim_gate_status": "candidate" if outcome == "positive" else "blocked_by_evidence",
            "blocking_reasons": [] if outcome == "positive" else ["no_improvement"],
            "source": "feedback_hook",
            "feedback_path": feedback_path,
            "scoreboard_path": scoreboard.get("scoreboard_path"),
            "frontier_path": (scoreboard.get("frontier") or {}).get("frontier_path"),
        }
        updated = store.update_claimability(quest_id=quest_id, trajectory_id=trajectory_id, claimability=claimability)
        self.events.append(
            "hook.feedback_ingested",
            {"quest_id": quest_id, "env_id": env_id, "trajectory_id": trajectory_id, "status": claimability["claim_gate_status"], "idea_id": idea_id},
            idempotency_key=f"hook.feedback_ingested:{quest_id}:{trajectory_id}:{feedback.get('run_id')}:trusted",
        )
        return {"ok": True, "hook": "feedback_ingested", "claimability": updated, "scoreboard": scoreboard}
