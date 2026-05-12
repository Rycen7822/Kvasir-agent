from __future__ import annotations

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def test_long_run_and_migration_docs_are_p4_native_and_do_not_overclaim_wall_clock_soak():
    usage = (PLUGIN_ROOT / "docs" / "USAGE.md").read_text(encoding="utf-8")
    long_run = (PLUGIN_ROOT / "docs" / "LONG_RUN.md").read_text(encoding="utf-8")
    migration = (PLUGIN_ROOT / "docs" / "MIGRATION.md").read_text(encoding="utf-8")
    combined = usage + "\n" + long_run + "\n" + migration

    for phrase in [
        "MCP-only default",
        "scripts/cs_mcp.py",
        "accelerated soak",
        "wall-clock soak",
        "do not claim stable ten-day wall-clock operation",
        "migrate legacy quests",
        "cs_goal_watchdog",
        "progress watchdog",
        "cs_checkpoint",
    ]:
        assert phrase in combined
    default_combined = usage + "\n" + long_run
    assert "CLI fallback" not in default_combined
    assert "scripts/csctl.py" not in default_combined
