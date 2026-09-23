from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ToolProfile:
    """Metadata for explicit Kvasir-agent MCP tool profiles."""

    name: str
    tool_names: tuple[str, ...]
    registers_mcp: bool = True
    mcp_gate: str | None = None
    deprecated: bool = False
    replacement: str | None = None


DEFAULT_PROFILE_NAME = "core"

CORE_TOOLS = (
    "ka_doctor",
    "ka_status",
    "ka_tool_schema",
    "ka_record_user_requirement",
    "ka_context_pack",
    "ka_resume_brief",
    "ka_checkpoint",
    "ka_pack_delta",
    "ka_skill_search",
    "ka_skill_load",
)

LEGACY_REGISTRY_ADMIN_TOOLS = (
    "ka_get_quest_state",
    "ka_set_active_quest",
    "ka_new_quest",
    "ka_manifest_init",
)

QUEST_MEMORY_TOOLS = (
    "ka_memory_search",
    "ka_memory_read",
    "ka_memory_list_recent",
    "ka_memory_write",
)

PHASE1_TOOLS = (
    "ka_environment_register",
    "ka_environment_validate",
    "ka_environment_show",
    "ka_feedback_ingest",
    "ka_trajectory_record",
    "ka_trajectory_search",
    "ka_trajectory_show",
)
PHASE1_EVIDENCE_TOOLS = ("ka_feedback_ingest", "ka_trajectory_search", "ka_trajectory_show")
PHASE3_PLANNING_TOOLS = ("ka_evolutionary_plan_round",)

EXECUTOR_LOCAL_TOOLS = (
    "ka_variant_create",
    "ka_variant_apply_patch",
    "ka_variant_check",
    "ka_variant_pack",
    "ka_implementer_patch_check",
    "ka_implementer_repair_patch",
    "ka_scheduler_submit",
    "ka_scheduler_status",
    "ka_worker_claim",
    "ka_worker_heartbeat",
    "ka_worker_collect",
    "ka_worker_upload_artifact",
    "ka_evolutionary_round_submit",
)

EVIDENCE_ADDITIONS = (
    *QUEST_MEMORY_TOOLS,
    "ka_manifest_record_baseline",
    "ka_manifest_validate",
    "ka_create_local_baseline",
    "ka_confirm_baseline",
    "ka_artifact_record",
    "ka_artifact_index",
    "ka_log_digest",
    *PHASE1_EVIDENCE_TOOLS,
    "ka_record_main_experiment",
    "ka_create_analysis_campaign",
    "ka_get_analysis_campaign",
    "ka_record_analysis_slice",
    "ka_claim_gate",
    "ka_submit_idea",
    "ka_get_method_scoreboard",
    "ka_get_optimization_frontier",
    "ka_record_negative_result",
    "ka_update_method_scoreboard",
)
EVIDENCE_TOOLS = tuple(dict.fromkeys((*CORE_TOOLS, *EVIDENCE_ADDITIONS)))
EXECUTION_PLANNING_TOOLS = tuple(dict.fromkeys((*CORE_TOOLS, *PHASE1_TOOLS, *PHASE3_PLANNING_TOOLS)))

FORMAL_RUN_TOOLS = tuple(dict.fromkeys((*EVIDENCE_TOOLS, "ka_bash_exec")))

LITERATURE_ADDITIONS = (
    *QUEST_MEMORY_TOOLS,
    "ka_strict_research_prepare",
    "ka_strict_research_record_candidate",
    "ka_strict_research_upsert_candidate",
    "ka_paper_fetch",
    "ka_record_literature_reading_note",
    "ka_strict_research_init_bibliography",
    "ka_paper_reliability_verify",
    "ka_arxiv",
)
LITERATURE_TOOLS = tuple(dict.fromkeys((*CORE_TOOLS, *LITERATURE_ADDITIONS)))

PAPER_WRITE_TOOLS = tuple(
    dict.fromkeys(
        (
            *LITERATURE_TOOLS,
            "ka_submit_paper_outline",
            "ka_submit_paper_bundle",
            "ka_refresh_summary",
            "ka_review_status",
        )
    )
)

AUTONOMOUS_TOOLS = tuple(
    dict.fromkeys(
        (
            *EVIDENCE_TOOLS,
            "ka_goal_context",
            "ka_goal_state",
            "ka_goal_next_action",
            "ka_goal_watchdog",
            "ka_queue_submit",
            "ka_queue_start_attempt",
            "ka_queue_status",
            "ka_queue_reconcile",
            "ka_runner_start",
            "ka_runner_status",
            "ka_trial_propose",
            "ka_trial_plan",
            "ka_trial_ready",
            "ka_trial_evaluate",
            "ka_trial_decide",
            "ka_trial_show",
            "ka_select_next_idea",
        )
    )
)

ADMIN_TOOLS = tuple(
    dict.fromkeys(
        (
            *AUTONOMOUS_TOOLS,
            *PAPER_WRITE_TOOLS,
            "ka_cost_status",
            "ka_soak_accelerated",
            "ka_soak_crash_resume",
            "ka_wiki_query_pack",
        )
    )
)

LEGACY_COMPAT_TOOLS = ADMIN_TOOLS
GOAL_TOOLS = EVIDENCE_TOOLS

LEGACY_STAGE_TOOL_ADDITIONS: Mapping[str, tuple[str, ...]] = {
    "scout": ("ka_new_quest", "ka_record_user_requirement", "ka_memory_search", "ka_memory_write", "ka_submit_idea"),
    "baseline": ("ka_create_local_baseline", "ka_confirm_baseline", "ka_manifest_record_baseline", "ka_manifest_validate"),
    "idea": ("ka_submit_idea", "ka_get_method_scoreboard", "ka_get_optimization_frontier", "ka_update_method_scoreboard", "ka_select_next_idea"),
    "experiment": ("ka_bash_exec", "ka_record_main_experiment", "ka_queue_submit", "ka_queue_status", "ka_runner_start", "ka_goal_watchdog"),
    "analysis": ("ka_create_analysis_campaign", "ka_get_analysis_campaign", "ka_record_analysis_slice", "ka_claim_gate"),
    "write": ("ka_submit_paper_outline", "ka_submit_paper_bundle", "ka_refresh_summary", "ka_paper_fetch"),
    "finalize": ("ka_checkpoint", "ka_resume_brief", "ka_refresh_summary", "ka_submit_paper_bundle"),
}

LEGACY_STAGE_ALIASES: Mapping[str, str] = {
    "analysis-campaign": "analysis",
    "analysis_campaign": "analysis",
    "optimize": "idea",
    "decision": "finalize",
}

# Backward-compatible exported names for old admin/autonomous tests. Default
# tools/list no longer uses these to filter agent-facing tool exposure.
STAGE_TOOL_ADDITIONS = LEGACY_STAGE_TOOL_ADDITIONS
STAGE_ALIASES = LEGACY_STAGE_ALIASES

PROFILES: Mapping[str, ToolProfile] = {
    "core": ToolProfile(name="core", tool_names=CORE_TOOLS),
    "evidence": ToolProfile(name="evidence", tool_names=EVIDENCE_TOOLS),
    "execution_planning": ToolProfile(name="execution_planning", tool_names=EXECUTION_PLANNING_TOOLS),
    "formal_run": ToolProfile(name="formal_run", tool_names=FORMAL_RUN_TOOLS),
    "literature": ToolProfile(name="literature", tool_names=LITERATURE_TOOLS),
    "paper_write": ToolProfile(name="paper_write", tool_names=PAPER_WRITE_TOOLS),
    "goal": ToolProfile(name="goal", tool_names=EVIDENCE_TOOLS, deprecated=True, replacement="evidence"),
    "autonomous": ToolProfile(name="autonomous", tool_names=AUTONOMOUS_TOOLS, registers_mcp=False),
    "executor_local": ToolProfile(name="executor_local", tool_names=EXECUTOR_LOCAL_TOOLS, registers_mcp=False, mcp_gate="executor_local"),
    "legacy_registry_admin": ToolProfile(name="legacy_registry_admin", tool_names=LEGACY_REGISTRY_ADMIN_TOOLS, registers_mcp=False),
    "admin": ToolProfile(name="admin", tool_names=ADMIN_TOOLS, registers_mcp=False),
    "legacy_compat": ToolProfile(name="legacy_compat", tool_names=LEGACY_COMPAT_TOOLS, registers_mcp=False),
}


def get_profile(name: str | None) -> ToolProfile:
    profile_name = name or DEFAULT_PROFILE_NAME
    if profile_name not in PROFILES:
        raise KeyError(f"Unknown Kvasir-agent profile: {profile_name}")
    return PROFILES[profile_name]


def normalize_stage(stage: str | None) -> tuple[str | None, bool]:
    if stage is None:
        return None, True
    raw = str(stage or "").strip().lower()
    if not raw:
        return None, True
    return LEGACY_STAGE_ALIASES.get(raw, raw), True


def get_profile_tool_names(name: str | None, *, stage: str | None = None) -> tuple[str, ...]:
    del stage
    return get_profile(name).tool_names
