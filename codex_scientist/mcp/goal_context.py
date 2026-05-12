from __future__ import annotations

from typing import Any

from codex_scientist.mcp.context import CodexScientistMcpContext
from codex_scientist.services.goal_loop import GoalLoopService
from codex_scientist.services.stage_router import StageRouter
from codex_scientist.profiles import get_profile_tool_names


def _service(args: dict[str, Any]) -> tuple[GoalLoopService, CodexScientistMcpContext]:
    context = CodexScientistMcpContext.from_env(args)
    return GoalLoopService(context.resolve_project_layout()), context


def _quest_id(context: CodexScientistMcpContext, args: dict[str, Any]) -> str | None:
    value = str(args.get("quest_id") or context.quest_id or "").strip()
    return value or None


def goal_state(args: dict[str, Any]) -> dict[str, Any]:
    service, context = _service(args)
    quest_id = _quest_id(context, args)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required for cs_goal_state", "error_type": "missing_argument", "recoverable": True}
    if any(key in args for key in ("active_stage", "current_gate", "completion_criteria", "next_action", "user_goal")):
        return service.write_state(
            quest_id,
            active_stage=args.get("active_stage") or args.get("stage"),
            current_gate=args.get("current_gate") if isinstance(args.get("current_gate"), dict) else None,
            completion_criteria=list(args.get("completion_criteria") or []) if "completion_criteria" in args else None,
            next_action=args.get("next_action") if isinstance(args.get("next_action"), dict) else None,
            user_goal=str(args.get("user_goal") or "").strip() or None,
        )
    state = service.read_state(quest_id)
    return {"ok": True, "path": str(service.state_path(quest_id)), "state": state, **state}


def goal_context(args: dict[str, Any]) -> dict[str, Any]:
    service, context = _service(args)
    quest_id = _quest_id(context, args)
    if not quest_id:
        stage = str(args.get("active_stage") or args.get("stage") or context.active_stage or "scout").strip() or "scout"
        route = StageRouter().route(user_goal=str(args.get("user_goal") or args.get("goal") or "").strip() or None, active_stage=stage, quest_snapshot={}, pending_gate={})
        tools = list(get_profile_tool_names("goal", stage=route.active_stage))
        payload = {
            "ok": True,
            "profile": "goal",
            "quest_id": None,
            "quest_root": None,
            "active_stage": route.active_stage,
            "current_gate": {},
            "completion_criteria": [],
            "allowed_tools_for_stage": tools,
            "stage_skills": [{"skill_id": route.stage_skill_id, "excerpt": "Unbound active-stage view; create or select a quest before writing state."}],
            "companion_skills": ([{"skill_id": route.companion_skill_id, "excerpt": "Optional bounded companion."}] if route.companion_skill_id else []),
            "blocked_reason": "missing_quest_id",
            "no_cli_text_guarantee": True,
        }
        payload["context"] = dict(payload)
        return payload
    return service.build_context(
        quest_id,
        user_goal=str(args.get("user_goal") or args.get("goal") or "").strip() or None,
        active_stage=args.get("active_stage") or args.get("stage"),
    )


def goal_next_action(args: dict[str, Any]) -> dict[str, Any]:
    service, context = _service(args)
    quest_id = _quest_id(context, args)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required for cs_goal_next_action", "error_type": "missing_argument", "recoverable": True}
    return service.next_action(quest_id, user_goal=str(args.get("user_goal") or args.get("goal") or "").strip() or None)
