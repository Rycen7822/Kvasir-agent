from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STAGE_IDS: tuple[str, ...] = (
    "scout",
    "strict-research",
    "baseline",
    "idea",
    "optimize",
    "experiment",
    "analysis-campaign",
    "write",
    "finalize",
    "decision",
)

COMPANION_SKILL_IDS: tuple[str, ...] = (
    "figure-polish",
    "intake-audit",
    "review",
    "rebuttal",
    "experiment-execution",
    "quest-handoffs",
    "writing-plans",
    "paper-reliability-verification",
)

_STAGE_ALIASES = {
    "analysis": "analysis-campaign",
    "analysis_campaign": "analysis-campaign",
    "strict_research": "strict-research",
    "literature": "strict-research",
}

_STAGE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("strict-research", ("strict", "literature", "related work", "survey", "paper search")),
    ("baseline", ("baseline", "reproduce", "benchmark")),
    ("experiment", ("experiment", "train", "run", "ablation")),
    ("analysis-campaign", ("analysis", "slice", "diagnose", "inspect")),
    ("write", ("write", "draft", "paper", "manuscript")),
    ("finalize", ("finalize", "submit", "release")),
    ("optimize", ("optimize", "frontier", "improve")),
    ("idea", ("idea", "hypothesis", "candidate")),
)

_COMPANION_BY_STAGE = {
    "experiment": "experiment-execution",
    "write": "writing-plans",
    "finalize": "quest-handoffs",
    "strict-research": "paper-reliability-verification",
    "analysis-campaign": "review",
}


@dataclass(frozen=True)
class StageRoute:
    active_stage: str
    stage_skill_id: str
    companion_skill_id: str | None = None
    reason: str = "default"


class StageRouter:
    """Deterministic active-stage router for Codex-native goal context."""

    def normalize_stage(self, stage: str | None) -> str | None:
        raw = str(stage or "").strip().lower()
        if not raw:
            return None
        normalized = _STAGE_ALIASES.get(raw, raw)
        return normalized if normalized in STAGE_IDS else None

    @staticmethod
    def _goal_stage(user_goal: str | None) -> tuple[str | None, str]:
        text = str(user_goal or "").strip().lower()
        if not text or text in {"continue", "继续", "next", "下一步"}:
            return None, "ambiguous_continue"
        for stage, keywords in _STAGE_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                return stage, f"keyword:{stage}"
        return None, "no_keyword"

    def route(
        self,
        *,
        user_goal: str | None = None,
        active_stage: str | None = None,
        quest_snapshot: dict[str, Any] | None = None,
        pending_gate: dict[str, Any] | None = None,
    ) -> StageRoute:
        gate_stage = self.normalize_stage((pending_gate or {}).get("stage") or (pending_gate or {}).get("active_stage"))
        if gate_stage:
            stage = gate_stage
            reason = "pending_gate"
        else:
            goal_stage, goal_reason = self._goal_stage(user_goal)
            existing_stage = self.normalize_stage(active_stage or (quest_snapshot or {}).get("active_stage"))
            if goal_stage:
                stage = goal_stage
                reason = goal_reason
            elif existing_stage:
                stage = existing_stage
                reason = "active_stage"
            else:
                stage = "scout"
                reason = goal_reason
        return StageRoute(
            active_stage=stage,
            stage_skill_id=stage,
            companion_skill_id=_COMPANION_BY_STAGE.get(stage),
            reason=reason,
        )
