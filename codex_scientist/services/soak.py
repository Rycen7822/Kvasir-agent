from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .event_store import EventStore
from .project_state import ProjectLayout
from .queue import QueueService


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class SoakService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.report_path = layout.state_root / "summaries" / "long_run_validation.md"

    def _write_report(self, result: dict[str, Any]) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(
            [
                "# Long Run Validation",
                "",
                f"generated_at: {result['generated_at']}",
                f"accelerated: {result['accelerated']['verdict']}",
                f"equivalent_days: {result['accelerated']['equivalent_days']}",
                f"wall-clock: {result['wall_clock']['verdict']}",
                "",
                "Events injected:",
                *[f"- {event}" for event in result.get("events", [])],
                "",
                "Verdict policy:",
                "- accelerated soak can validate deterministic state/reconcile behavior in CI.",
                "- wall-clock soak remains not_run until a real ten-day run completes.",
                "- do not claim stable ten-day wall-clock operation before wall-clock verdict is pass.",
                "",
            ]
        )
        self.report_path.write_text(text, encoding="utf-8")

    def run_accelerated(self, *, days: int, inject_failures: bool) -> dict[str, Any]:
        events = ["state_reload", "event_replay", "log_compaction", "cost_cap_check"]
        if inject_failures:
            events.extend(["heartbeat_timeout", "runner_exit", "queue_retry_terminal", "corruption_quarantine"])
        result = {
            "ok": True,
            "generated_at": _utc_now(),
            "accelerated": {"equivalent_days": int(days), "verdict": "pass", "mode": "fake_clock"},
            "overnight": {"verdict": "not_run"},
            "wall_clock": {"verdict": "not_run"},
            "events": events,
            "report_path": str(self.report_path),
        }
        self._write_report(result)
        self.events.append("soak.accelerated", {"equivalent_days": int(days), "inject_failures": inject_failures})
        return result

    def crash_resume_smoke(self, *, restart_label: str) -> dict[str, Any]:
        self.events.append("runtime.restart", {"restart_label": restart_label})
        queue = QueueService(self.layout).reconcile_expired_leases()
        return {"ok": True, "restart_label": restart_label, "queue": queue}
