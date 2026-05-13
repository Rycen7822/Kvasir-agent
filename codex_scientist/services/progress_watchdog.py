from __future__ import annotations

from typing import Any

from .project_state import ProjectLayout
from .watchdog import WatchdogService


class ProgressWatchdogService:
    """Manual long-run diagnostics for CodexScientist quests.

    Upgrade 6 makes progress watchdog passive: it reports stale runner state
    without writing checkpoint pressure, progress counters, or goal-loop gates.
    """

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout

    def reconcile_goal_runtime(self, *, quest_id: str, timeout_seconds: int) -> dict[str, Any]:
        result = WatchdogService(self.layout).reconcile_stale_runs(timeout_seconds=timeout_seconds)
        stuck_runs = list(result.get("stuck_runs") or [])
        return {
            "ok": True,
            "quest_id": quest_id,
            "stuck_runs": stuck_runs,
            "diagnostic": {
                "runner_stuck": bool(stuck_runs),
                "stuck_run_count": len(stuck_runs),
                "recommended_evidence": ["cs_log_digest", "cs_runner_status", "cs_queue_reconcile"] if stuck_runs else [],
            },
            "watchdog": result,
        }
