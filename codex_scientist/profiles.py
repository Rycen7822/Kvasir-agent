from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ToolProfile:
    """Metadata for an explicit Codex-Scientist tool profile.

    Profiles describe curated tool groups. The stable MCP server is the default
    high-frequency control plane; CLI fallback can still use the same profile
    metadata for audited surfaces.
    """

    name: str
    tool_names: tuple[str, ...]
    registers_mcp: bool = True


DEFAULT_PROFILE_NAME = "core"

PROFILES: Mapping[str, ToolProfile] = {
    "core": ToolProfile(
        name="core",
        tool_names=(
            "cs_doctor",
            "cs_list_quests",
            "cs_get_quest_state",
            "cs_new_quest",
            "cs_set_active_quest",
            "cs_record_user_requirement",
            "cs_memory_search",
            "cs_memory_write",
            "cs_memory_list_recent",
            "cs_artifact_record",
            "cs_events",
            "cs_refresh_summary",
        ),
    ),
    "dl_trial": ToolProfile(
        name="dl_trial",
        tool_names=(
            "cs_create_local_baseline",
            "cs_confirm_baseline",
            "cs_waive_baseline",
            "cs_attach_baseline",
            "cs_submit_idea",
            "cs_record_main_experiment",
            "cs_bash_exec",
        ),
    ),
    "review": ToolProfile(
        name="review",
        tool_names=(
            "cs_get_paper_contract_health",
            "cs_get_conversation_context",
            "cs_list_paper_outlines",
            "cs_refresh_summary",
        ),
    ),
}


def get_profile(name: str | None) -> ToolProfile:
    profile_name = name or DEFAULT_PROFILE_NAME
    if profile_name not in PROFILES:
        raise KeyError(f"Unknown Codex-Scientist profile: {profile_name}")
    return PROFILES[profile_name]
