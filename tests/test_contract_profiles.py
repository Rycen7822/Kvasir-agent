from __future__ import annotations

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def test_default_profiles_are_metadata_only_and_do_not_register_mcp():
    from codex_scientist.profiles import DEFAULT_PROFILE_NAME, PROFILES, get_profile

    assert DEFAULT_PROFILE_NAME == "core"
    core = get_profile(None)
    assert core.name == "core"
    assert 1 <= len(core.tool_names) <= 12
    assert set(core.tool_names) <= {schema["name"] for schema in __import__("deepscientist_native.schemas", fromlist=["PUBLIC_SCHEMAS"]).PUBLIC_SCHEMAS}

    for profile in PROFILES.values():
        assert not profile.registers_mcp
        assert profile.tool_names

    manifest_text = (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    assert "mcpServers" not in manifest_text


def test_profile_lookup_rejects_all_tools_profile_by_default():
    from codex_scientist.profiles import get_profile

    try:
        get_profile("all")
    except KeyError as exc:
        assert "all" in str(exc)
    else:
        raise AssertionError("default profile registry must not expose an all-tools profile")
