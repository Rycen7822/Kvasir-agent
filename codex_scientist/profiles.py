from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ToolProfile:
    """Metadata for explicit CodexScientist MCP tool profiles."""

    name: str
    tool_names: tuple[str, ...]
    registers_mcp: bool = True


DEFAULT_PROFILE_NAME = "core"

CORE_TOOLS = (
    "cs_doctor",
    "cs_status",
    "cs_goal_context",
    "cs_goal_state",
    "cs_goal_next_action",
    "cs_tool_schema",
    "cs_get_quest_state",
    "cs_set_active_quest",
    "cs_context_pack",
    "cs_resume_brief",
    "cs_checkpoint",
    "cs_pack_delta",
    "cs_skill_search",
    "cs_skill_load",
)

GOAL_ADDITIONS = (
    "cs_new_quest",
    "cs_record_user_requirement",
    "cs_memory_search",
    "cs_create_local_baseline",
    "cs_confirm_baseline",
    "cs_submit_idea",
    "cs_get_method_scoreboard",
    "cs_get_optimization_frontier",
    "cs_record_negative_result",
    "cs_update_method_scoreboard",
    "cs_select_next_idea",
    "cs_claim_gate",
    "cs_record_main_experiment",
    "cs_create_analysis_campaign",
    "cs_record_analysis_slice",
    "cs_bash_exec",
    "cs_submit_paper_outline",
    "cs_submit_paper_bundle",
    "cs_manifest_init",
    "cs_manifest_validate",
    "cs_queue_submit",
    "cs_queue_status",
    "cs_runner_start",
    "cs_runner_status",
    "cs_goal_watchdog",
    "cs_log_digest",
    "cs_artifact_index",
    "cs_trial_propose",
    "cs_trial_plan",
    "cs_trial_ready",
    "cs_trial_evaluate",
    "cs_trial_decide",
    "cs_trial_show",
)

GOAL_TOOLS = tuple(dict.fromkeys((*CORE_TOOLS, *GOAL_ADDITIONS)))

STAGE_TOOL_ADDITIONS: Mapping[str, tuple[str, ...]] = {
    "scout": (
        "cs_new_quest",
        "cs_record_user_requirement",
        "cs_memory_search",
        "cs_memory_write",
        "cs_submit_idea",
        "cs_get_method_scoreboard",
        "cs_get_optimization_frontier",
    ),
    "baseline": (
        "cs_create_local_baseline",
        "cs_confirm_baseline",
        "cs_manifest_init",
        "cs_manifest_record_baseline",
        "cs_manifest_validate",
    ),
    "idea": (
        "cs_submit_idea",
        "cs_get_method_scoreboard",
        "cs_get_optimization_frontier",
        "cs_update_method_scoreboard",
        "cs_select_next_idea",
        "cs_trial_propose",
        "cs_trial_plan",
    ),
    "experiment": (
        "cs_bash_exec",
        "cs_record_main_experiment",
        "cs_queue_submit",
        "cs_queue_status",
        "cs_runner_start",
        "cs_goal_watchdog",
        "cs_trial_plan",
        "cs_trial_ready",
        "cs_trial_evaluate",
    ),
    "analysis": (
        "cs_create_analysis_campaign",
        "cs_get_analysis_campaign",
        "cs_record_analysis_slice",
        "cs_claim_gate",
        "cs_get_method_scoreboard",
        "cs_get_optimization_frontier",
    ),
    "write": (
        "cs_submit_paper_outline",
        "cs_submit_paper_bundle",
        "cs_refresh_summary",
        "cs_paper_fetch",
    ),
    "finalize": (
        "cs_checkpoint",
        "cs_resume_brief",
        "cs_refresh_summary",
        "cs_submit_paper_bundle",
    ),
}

STAGE_ALIASES: Mapping[str, str] = {
    "analysis-campaign": "analysis",
    "analysis_campaign": "analysis",
    "strict-research": "scout",
    "strict_research": "scout",
    "optimize": "idea",
    "decision": "finalize",
}

PROFILES: Mapping[str, ToolProfile] = {
    "core": ToolProfile(name="core", tool_names=CORE_TOOLS),
    "goal": ToolProfile(name="goal", tool_names=GOAL_TOOLS),
    "admin": ToolProfile(
        name="admin",
        tool_names=GOAL_TOOLS,
        registers_mcp=False,
    ),
}


def get_profile(name: str | None) -> ToolProfile:
    profile_name = name or DEFAULT_PROFILE_NAME
    if profile_name not in PROFILES:
        raise KeyError(f"Unknown CodexScientist profile: {profile_name}")
    return PROFILES[profile_name]


def get_profile_tool_names(name: str | None, *, stage: str | None = None) -> tuple[str, ...]:
    profile = get_profile(name)
    if stage is None or profile.name != "goal":
        return profile.tool_names
    stage_key = STAGE_ALIASES.get(str(stage or "").strip().lower(), str(stage or "").strip().lower())
    additions = STAGE_TOOL_ADDITIONS.get(stage_key, STAGE_TOOL_ADDITIONS["scout"])
    allowed = set(profile.tool_names)
    return tuple(tool for tool in dict.fromkeys((*CORE_TOOLS, *additions)) if tool in allowed)
