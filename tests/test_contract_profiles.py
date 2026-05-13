from __future__ import annotations

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def test_default_profiles_are_curated_mcp_metadata_without_all_tools_surface():
    from codex_scientist.mcp.tool_registry import list_tool_specs
    from codex_scientist.profiles import DEFAULT_PROFILE_NAME, PROFILES, get_profile

    assert DEFAULT_PROFILE_NAME == "core"
    core = get_profile(None)
    assert core.name == "core"
    assert 1 <= len(core.tool_names) <= 12
    assert "cs_goal_state" not in core.tool_names
    assert "cs_goal_next_action" not in core.tool_names
    assert "cs_bash_exec" not in core.tool_names
    assert set(core.tool_names) == {spec.name for spec in list_tool_specs()}

    for profile in PROFILES.values():
        assert profile.tool_names
    assert PROFILES["core"].registers_mcp
    assert PROFILES["evidence"].registers_mcp
    assert PROFILES["goal"].registers_mcp
    assert PROFILES["goal"].deprecated
    assert not PROFILES["autonomous"].registers_mcp
    assert not PROFILES["admin"].registers_mcp
    assert not PROFILES["legacy_compat"].registers_mcp

    manifest_text = (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    assert "mcpServers" not in manifest_text
    assert "MCP-only default" in manifest_text
    assert "scripts/csctl.py" not in manifest_text
    assert "CLI fallback" not in manifest_text


def test_profile_lookup_rejects_all_tools_profile_by_default():
    from codex_scientist.profiles import get_profile

    try:
        get_profile("all")
    except KeyError as exc:
        assert "all" in str(exc)
    else:
        raise AssertionError("default profile registry must not expose an all-tools profile")
