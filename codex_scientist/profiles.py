from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ToolProfile:
    """Metadata for an explicit Codex-Scientist tool profile.

    Profiles are metadata only in the default native plugin. They do not register
    MCP servers or change the plugin manifest; adapters may use them later to
    expose a small, audited surface.
    """

    name: str
    tool_names: tuple[str, ...]
    registers_mcp: bool = False


DEFAULT_PROFILE_NAME = "core"

PROFILES: Mapping[str, ToolProfile] = {
    "core": ToolProfile(
        name="core",
        tool_names=(
            "ds_doctor",
            "ds_list_quests",
            "ds_get_quest_state",
            "ds_new_quest",
            "ds_set_active_quest",
            "ds_record_user_requirement",
            "ds_memory_search",
            "ds_memory_write",
            "ds_memory_list_recent",
            "ds_artifact_record",
            "ds_events",
            "ds_refresh_summary",
        ),
    ),
    "dl_trial": ToolProfile(
        name="dl_trial",
        tool_names=(
            "ds_create_local_baseline",
            "ds_confirm_baseline",
            "ds_waive_baseline",
            "ds_attach_baseline",
            "ds_submit_idea",
            "ds_record_main_experiment",
            "ds_bash_exec",
        ),
    ),
    "review": ToolProfile(
        name="review",
        tool_names=(
            "ds_get_paper_contract_health",
            "ds_get_conversation_context",
            "ds_list_paper_outlines",
            "ds_refresh_summary",
        ),
    ),
}


def get_profile(name: str | None) -> ToolProfile:
    profile_name = name or DEFAULT_PROFILE_NAME
    if profile_name not in PROFILES:
        raise KeyError(f"Unknown Codex-Scientist profile: {profile_name}")
    return PROFILES[profile_name]
