from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .event_store import EventStore
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class CostApprovalService:
    def __init__(self, layout: ProjectLayout, *, daily_cap_usd: float) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.daily_cap_usd = float(daily_cap_usd)
        self.cost_dir = layout.state_root / "costs"
        self.path = self.cost_dir / "cost.json"

    def _write(self, decision: dict[str, Any]) -> None:
        self.cost_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def status(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"ok": True, "configured": False, "path": str(self.path), "daily_cap_usd": self.daily_cap_usd}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"ok": False, "error": "Cost file is corrupt", "error_type": "cost_corrupt", "recoverable": True, "path": str(self.path)}
        if not isinstance(loaded, dict):
            loaded = {}
        loaded.setdefault("ok", True)
        loaded.setdefault("configured", True)
        loaded.setdefault("path", str(self.path))
        return loaded

    def evaluate_action(self, *, action_class: str, estimated_cost_usd: float, approved: bool = False) -> dict[str, Any]:
        estimated = float(estimated_cost_usd)
        normalized = action_class.lower()
        if normalized == "read-only local":
            decision = "allowed"
            requires = False
        elif "destructive" in normalized:
            decision = "allowed" if approved else "blocked_destructive"
            requires = not approved
        elif "scheduled" in normalized or "recurring" in normalized:
            decision = "allowed" if approved else "blocked_approval"
            requires = not approved
        elif estimated > self.daily_cap_usd:
            decision = "blocked_budget"
            requires = True
        elif "gpu" in normalized or "cloud" in normalized:
            decision = "allowed" if approved else "blocked_approval"
            requires = not approved
        else:
            decision = "allowed"
            requires = False
        payload = {
            "ok": True,
            "action_class": action_class,
            "estimated_cost_usd": estimated,
            "daily_cap_usd": self.daily_cap_usd,
            "remaining_budget_usd": max(self.daily_cap_usd - estimated, 0.0),
            "decision": decision,
            "requires_approval": requires,
            "updated_at": _utc_now(),
            "path": str(self.path),
        }
        self._write(payload)
        self.events.append("cost.action_evaluated", {"action_class": action_class, "decision": decision})
        return payload
