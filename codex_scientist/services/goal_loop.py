from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_scientist.profiles import get_profile_tool_names

from .project_state import ProjectLayout
from .stage_router import StageRouter


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


_DEFAULT_ACTIONS: dict[str, dict[str, Any]] = {
    "scout": {
        "action_type": "record_requirement",
        "required_tool": "cs_record_user_requirement",
        "required_inputs": ["quest_id", "message"],
        "blocking_reason": None,
        "done_when": "user requirement and initial research constraints are durable",
    },
    "strict-research": {
        "action_type": "screen_literature",
        "required_tool": "cs_memory_search",
        "required_inputs": ["query"],
        "blocking_reason": None,
        "done_when": "candidate literature evidence is recorded or explicitly deferred",
    },
    "baseline": {
        "action_type": "establish_baseline",
        "required_tool": "cs_create_local_baseline",
        "required_inputs": ["quest_id", "baseline_id"],
        "blocking_reason": "baseline_missing",
        "done_when": "baseline is confirmed or explicitly waived with rationale",
    },
    "idea": {
        "action_type": "submit_idea",
        "required_tool": "cs_submit_idea",
        "required_inputs": ["quest_id", "title"],
        "blocking_reason": None,
        "done_when": "one candidate idea has evidence and selection scores",
    },
    "optimize": {
        "action_type": "select_frontier",
        "required_tool": "cs_get_optimization_frontier",
        "required_inputs": ["quest_id"],
        "blocking_reason": None,
        "done_when": "frontier is refreshed and one next idea is selected",
    },
    "experiment": {
        "action_type": "record_experiment",
        "required_tool": "cs_record_main_experiment",
        "required_inputs": ["quest_id", "run_id"],
        "blocking_reason": None,
        "done_when": "main experiment evidence, metric rows, and conclusion are recorded",
    },
    "analysis-campaign": {
        "action_type": "record_analysis",
        "required_tool": "cs_record_analysis_slice",
        "required_inputs": ["quest_id", "campaign_id", "slice_id"],
        "blocking_reason": None,
        "done_when": "next analysis slice is recorded with evidence",
    },
    "write": {
        "action_type": "submit_paper_bundle",
        "required_tool": "cs_submit_paper_bundle",
        "required_inputs": ["quest_id"],
        "blocking_reason": None,
        "done_when": "paper bundle references claim-evidence-backed artifacts",
    },
    "finalize": {
        "action_type": "checkpoint_finalize",
        "required_tool": "cs_checkpoint",
        "required_inputs": ["phase", "completed", "next_action"],
        "blocking_reason": None,
        "done_when": "final checkpoint and handoff summary are durable",
    },
    "decision": {
        "action_type": "record_decision",
        "required_tool": "cs_checkpoint",
        "required_inputs": ["phase", "decisions"],
        "blocking_reason": None,
        "done_when": "decision gate is recorded with validation evidence",
    },
}

_SKILL_EXCERPTS = {
    "scout": "Scout only the current requirement and durable constraints; do not load downstream stages.",
    "strict-research": "Screen literature conservatively and record evidence before idea expansion.",
    "baseline": "Establish or waive the baseline gate before experiment claims.",
    "idea": "Submit one evidence-backed idea candidate and keep lineage explicit.",
    "optimize": "Use frontier state and prior evidence to pick the next bounded improvement.",
    "experiment": "Run or record one bounded experiment and persist metric evidence.",
    "analysis-campaign": "Process only the active analysis slice and avoid paper-facing claims until evidence exists.",
    "write": "Draft only from claim-evidence-backed artifacts and selected outline state.",
    "finalize": "Create durable checkpoint, handoff, and closure evidence.",
    "decision": "Resolve the active decision gate with explicit validation.",
}


class GoalLoopService:
    """Project-local goal loop state, context, and next-action gates."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.router = StageRouter()

    def state_path(self, quest_id: str) -> Path:
        quest = self.layout.ensure_quest_layout(quest_id)
        return quest.runtime_dir / "goal_state.json"

    def read_state(self, quest_id: str) -> dict[str, Any]:
        path = self.state_path(quest_id)
        if not path.exists():
            return {
                "schema_version": 1,
                "quest_id": self.layout.quest_layout(quest_id).quest_id,
                "quest_root": str(self.layout.quest_root_for(quest_id)),
                "active_stage": "scout",
                "current_gate": {},
                "completion_criteria": [],
                "next_action": _DEFAULT_ACTIONS["scout"],
                "updated_at": _utc_now(),
            }
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}

    def write_state(
        self,
        quest_id: str,
        *,
        active_stage: str | None = None,
        current_gate: dict[str, Any] | None = None,
        completion_criteria: list[Any] | None = None,
        next_action: dict[str, Any] | None = None,
        user_goal: str | None = None,
    ) -> dict[str, Any]:
        existing = self.read_state(quest_id)
        route = self.router.route(
            user_goal=user_goal,
            active_stage=active_stage or existing.get("active_stage"),
            quest_snapshot=existing,
            pending_gate=current_gate or existing.get("current_gate") or {},
        )
        stage = route.active_stage
        gate = dict(current_gate if current_gate is not None else existing.get("current_gate") or {})
        if gate:
            gate.setdefault("stage", stage)
        action = dict(next_action if next_action is not None else existing.get("next_action") or {}) or self.default_next_action(stage)
        action.setdefault("stage", stage)
        state = {
            "schema_version": 1,
            "quest_id": self.layout.quest_layout(quest_id).quest_id,
            "quest_root": str(self.layout.quest_root_for(quest_id)),
            "active_stage": stage,
            "current_gate": gate,
            "completion_criteria": list(completion_criteria if completion_criteria is not None else existing.get("completion_criteria") or []),
            "next_action": action,
            "updated_at": _utc_now(),
        }
        path = self.state_path(quest_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        return {"ok": True, "path": str(path), "state": state, **state}

    def default_next_action(self, stage: str) -> dict[str, Any]:
        return dict(_DEFAULT_ACTIONS.get(stage) or _DEFAULT_ACTIONS["scout"])

    def next_action(self, quest_id: str, *, user_goal: str | None = None) -> dict[str, Any]:
        state = self.read_state(quest_id)
        route = self.router.route(
            user_goal=user_goal,
            active_stage=state.get("active_stage"),
            quest_snapshot=state,
            pending_gate=state.get("current_gate") or {},
        )
        action = self.default_next_action(route.active_stage)
        gate = state.get("current_gate") if isinstance(state.get("current_gate"), dict) else {}
        if gate:
            action.update({k: v for k, v in gate.items() if k in {"action_type", "blocking_reason", "required_tool", "required_inputs", "done_when", "run_id", "job_id", "trial_id"} and v})
        action["stage"] = route.active_stage
        return {
            "ok": True,
            "quest_id": self.layout.quest_layout(quest_id).quest_id,
            "quest_root": str(self.layout.quest_root_for(quest_id)),
            "active_stage": route.active_stage,
            "next_action": action,
            "route_reason": route.reason,
            "no_cli_text_guarantee": True,
        }

    def build_context(self, quest_id: str, *, user_goal: str | None = None, active_stage: str | None = None) -> dict[str, Any]:
        state = self.read_state(quest_id)
        route = self.router.route(
            user_goal=user_goal,
            active_stage=active_stage or state.get("active_stage"),
            quest_snapshot=state,
            pending_gate=state.get("current_gate") or {},
        )
        allowed_tools = list(get_profile_tool_names("goal", stage=route.active_stage))
        next_action = self.next_action(quest_id, user_goal=user_goal)["next_action"]
        stage_skill = {
            "skill_id": route.stage_skill_id,
            "excerpt": _SKILL_EXCERPTS.get(route.stage_skill_id, "Use only the active stage context."),
        }
        companions = []
        if route.companion_skill_id:
            companions.append({"skill_id": route.companion_skill_id, "excerpt": "Optional bounded companion; load at most this one if needed."})
        context = {
            "quest_id": self.layout.quest_layout(quest_id).quest_id,
            "quest_root": str(self.layout.quest_root_for(quest_id)),
            "active_stage": route.active_stage,
            "current_gate": state.get("current_gate") or {},
            "completion_criteria": list(state.get("completion_criteria") or []),
            "latest_baseline_state": {},
            "latest_idea_frontier_summary": {},
            "latest_experiment_summary": {},
            "latest_analysis_campaign_summary": {},
            "next_required_action": next_action,
            "allowed_tools_for_stage": allowed_tools,
            "stage_skills": [stage_skill],
            "companion_skills": companions,
            "no_cli_text_guarantee": True,
            "route_reason": route.reason,
        }
        return {"ok": True, **context, "context": context}
