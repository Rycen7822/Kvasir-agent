from __future__ import annotations

from codex_scientist.services.stage_router import StageRouter


def test_stage_router_keeps_active_stage_for_ambiguous_continue():
    router = StageRouter()
    routed = router.route(user_goal="继续", active_stage="experiment", quest_snapshot={}, pending_gate={})

    assert routed.active_stage == "experiment"
    assert routed.stage_skill_id == "experiment"
    assert routed.companion_skill_id == "experiment-execution"


def test_stage_router_prefers_pending_gate_then_goal_keywords():
    router = StageRouter()
    gated = router.route(
        user_goal="write final summary",
        active_stage="experiment",
        quest_snapshot={},
        pending_gate={"stage": "analysis-campaign"},
    )
    assert gated.active_stage == "analysis-campaign"
    assert gated.stage_skill_id == "analysis-campaign"

    strict = router.route(user_goal="do strict literature research before ideas", active_stage=None, quest_snapshot={}, pending_gate={})
    assert strict.active_stage == "strict-research"
    assert strict.stage_skill_id == "strict-research"

    writing = router.route(user_goal="write the paper", active_stage=None, quest_snapshot={}, pending_gate={})
    assert writing.active_stage == "write"
    assert writing.companion_skill_id == "writing-plans"
