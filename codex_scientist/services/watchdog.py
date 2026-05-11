from __future__ import annotations

from datetime import datetime

from .project_state import ProjectLayout
from .runner import RunnerService


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


class WatchdogService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.runner = RunnerService(layout)

    def reconcile_stale_runs(self, *, timeout_seconds: int) -> dict:
        now = datetime.now().astimezone()
        stuck: list[str] = []
        for run in self.runner.list_runs():
            if run.get("status") != "running":
                continue
            heartbeat = _parse_iso(run["heartbeat_at"])
            if (now - heartbeat).total_seconds() >= timeout_seconds:
                self.runner.update_status(run["run_id"], "stuck")
                stuck.append(run["run_id"])
        return {"ok": True, "stuck_runs": stuck}
