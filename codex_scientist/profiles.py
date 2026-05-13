from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ToolProfile:
    """Metadata for explicit CodexScientist MCP tool profiles."""

    name: str
    tool_names: tuple[str, ...]
    registers_mcp: bool = True
    deprecated: bool = False
    replacement: str | None = None


DEFAULT_PROFILE_NAME = "core"

CORE_TOOLS = (
    "cs_doctor",
    "cs_status",
    "cs_tool_schema",
    "cs_get_quest_state",
    "cs_set_active_quest",
    "cs_new_quest",
    "cs_record_user_requirement",
    "cs_context_pack",
    "cs_resume_brief",
    "cs_checkpoint",
    "cs_pack_delta",
)

QUEST_MEMORY_TOOLS = (
    "cs_memory_search",
    "cs_memory_read",
    "cs_memory_list_recent",
    "cs_memory_write",
)

EVIDENCE_ADDITIONS = (
    *QUEST_MEMORY_TOOLS,
    "cs_manifest_init",
    "cs_manifest_record_baseline",
    "cs_manifest_validate",
    "cs_create_local_baseline",
    "cs_confirm_baseline",
    "cs_artifact_record",
    "cs_artifact_index",
    "cs_log_digest",
    "cs_record_main_experiment",
    "cs_record_analysis_slice",
    "cs_claim_gate",
    "cs_submit_idea",
    "cs_get_method_scoreboard",
    "cs_get_optimization_frontier",
    "cs_record_negative_result",
    "cs_update_method_scoreboard",
)
EVIDENCE_TOOLS = tuple(dict.fromkeys((*CORE_TOOLS, *EVIDENCE_ADDITIONS)))

FORMAL_RUN_TOOLS = tuple(dict.fromkeys((*EVIDENCE_TOOLS, "cs_bash_exec")))

LITERATURE_ADDITIONS = (
    *QUEST_MEMORY_TOOLS,
    "cs_strict_research_prepare",
    "cs_strict_research_record_candidate",
    "cs_strict_research_upsert_candidate",
    "cs_paper_fetch",
    "cs_record_literature_reading_note",
    "cs_strict_research_init_bibliography",
    "cs_paper_reliability_verify",
    "cs_arxiv",
)
LITERATURE_TOOLS = tuple(dict.fromkeys((*CORE_TOOLS, *LITERATURE_ADDITIONS)))

PAPER_WRITE_TOOLS = tuple(
    dict.fromkeys(
        (
            *LITERATURE_TOOLS,
            "cs_submit_paper_outline",
            "cs_submit_paper_bundle",
            "cs_refresh_summary",
            "cs_review_status",
        )
    )
)

AUTONOMOUS_TOOLS = tuple(
    dict.fromkeys(
        (
            *EVIDENCE_TOOLS,
            "cs_goal_context",
            "cs_goal_state",
            "cs_goal_next_action",
            "cs_goal_watchdog",
            "cs_queue_submit",
            "cs_queue_start_attempt",
            "cs_queue_status",
            "cs_queue_reconcile",
            "cs_runner_start",
            "cs_runner_status",
            "cs_trial_propose",
            "cs_trial_plan",
            "cs_trial_ready",
            "cs_trial_evaluate",
            "cs_trial_decide",
            "cs_trial_show",
            "cs_select_next_idea",
        )
    )
)

ADMIN_TOOLS = tuple(
    dict.fromkeys(
        (
            *AUTONOMOUS_TOOLS,
            *PAPER_WRITE_TOOLS,
            "cs_cost_status",
            "cs_soak_accelerated",
            "cs_soak_crash_resume",
            "cs_wiki_query_pack",
        )
    )
)

LEGACY_COMPAT_TOOLS = ADMIN_TOOLS
GOAL_TOOLS = EVIDENCE_TOOLS

LEGACY_STAGE_TOOL_ADDITIONS: Mapping[str, tuple[str, ...]] = {
    "scout": ("cs_new_quest", "cs_record_user_requirement", "cs_memory_search", "cs_memory_write", "cs_submit_idea"),
    "baseline": ("cs_create_local_baseline", "cs_confirm_baseline", "cs_manifest_init", "cs_manifest_record_baseline", "cs_manifest_validate"),
    "idea": ("cs_submit_idea", "cs_get_method_scoreboard", "cs_get_optimization_frontier", "cs_update_method_scoreboard", "cs_select_next_idea"),
    "experiment": ("cs_bash_exec", "cs_record_main_experiment", "cs_queue_submit", "cs_queue_status", "cs_runner_start", "cs_goal_watchdog"),
    "analysis": ("cs_create_analysis_campaign", "cs_get_analysis_campaign", "cs_record_analysis_slice", "cs_claim_gate"),
    "write": ("cs_submit_paper_outline", "cs_submit_paper_bundle", "cs_refresh_summary", "cs_paper_fetch"),
    "finalize": ("cs_checkpoint", "cs_resume_brief", "cs_refresh_summary", "cs_submit_paper_bundle"),
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
    "formal_run": ToolProfile(name="formal_run", tool_names=FORMAL_RUN_TOOLS),
    "literature": ToolProfile(name="literature", tool_names=LITERATURE_TOOLS),
    "paper_write": ToolProfile(name="paper_write", tool_names=PAPER_WRITE_TOOLS),
    "goal": ToolProfile(name="goal", tool_names=EVIDENCE_TOOLS, deprecated=True, replacement="evidence"),
    "autonomous": ToolProfile(name="autonomous", tool_names=AUTONOMOUS_TOOLS, registers_mcp=False),
    "admin": ToolProfile(name="admin", tool_names=ADMIN_TOOLS, registers_mcp=False),
    "legacy_compat": ToolProfile(name="legacy_compat", tool_names=LEGACY_COMPAT_TOOLS, registers_mcp=False),
}


def get_profile(name: str | None) -> ToolProfile:
    profile_name = name or DEFAULT_PROFILE_NAME
    if profile_name not in PROFILES:
        raise KeyError(f"Unknown CodexScientist profile: {profile_name}")
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
