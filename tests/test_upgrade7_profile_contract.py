from __future__ import annotations

from codex_scientist.mcp.tool_registry import tools_list_payload

PHASE1_TOOLS = {
    "cs_environment_register",
    "cs_environment_validate",
    "cs_environment_show",
    "cs_feedback_ingest",
    "cs_trajectory_record",
    "cs_trajectory_search",
    "cs_trajectory_show",
}
PLANNING_TOOLS = {"cs_evolutionary_plan_round"}
EVIDENCE_PHASE1_TOOLS = {"cs_feedback_ingest", "cs_trajectory_search", "cs_trajectory_show"}
EXECUTOR_TOOLS = {
    "cs_variant_create",
    "cs_variant_apply_patch",
    "cs_variant_check",
    "cs_variant_pack",
    "cs_implementer_patch_check",
    "cs_implementer_repair_patch",
    "cs_scheduler_submit",
    "cs_worker_claim",
    "cs_evolutionary_round_submit",
}


def _names(payload: dict) -> set[str]:
    assert payload.get("ok") is True, payload
    return {tool["name"] for tool in payload.get("tools", [])}


def test_core_profile_excludes_phase1_and_executor_tools():
    names = _names(tools_list_payload({}))
    assert names.isdisjoint(PHASE1_TOOLS | PLANNING_TOOLS), sorted(names & (PHASE1_TOOLS | PLANNING_TOOLS))
    assert names.isdisjoint(EXECUTOR_TOOLS), sorted(names & EXECUTOR_TOOLS)


def test_evidence_profile_only_gets_low_risk_phase1_tools():
    names = _names(tools_list_payload({"profile": "evidence"}))
    assert EVIDENCE_PHASE1_TOOLS <= names, sorted(EVIDENCE_PHASE1_TOOLS - names)
    assert names.isdisjoint(PHASE1_TOOLS - EVIDENCE_PHASE1_TOOLS), sorted(names & (PHASE1_TOOLS - EVIDENCE_PHASE1_TOOLS))
    assert names.isdisjoint(PLANNING_TOOLS), sorted(names & PLANNING_TOOLS)
    assert names.isdisjoint(EXECUTOR_TOOLS), sorted(names & EXECUTOR_TOOLS)


def test_execution_planning_profile_exposes_all_phase1_tools_without_executor_tools():
    payload = tools_list_payload({"profile": "execution_planning"})
    names = _names(payload)
    assert payload.get("profile") == "execution_planning"
    assert PHASE1_TOOLS <= names, sorted(PHASE1_TOOLS - names)
    assert PLANNING_TOOLS <= names, sorted(PLANNING_TOOLS - names)
    assert names.isdisjoint(EXECUTOR_TOOLS), sorted(names & EXECUTOR_TOOLS)


def test_executor_local_profile_exists_but_is_not_registered_for_default_mcp():
    payload = tools_list_payload({"profile": "executor_local"})
    assert payload.get("ok") is False, payload
    assert payload.get("error_type") == "profile_not_registered_for_mcp"
    assert payload.get("recoverable") is True
    assert payload.get("profile") == "executor_local"
