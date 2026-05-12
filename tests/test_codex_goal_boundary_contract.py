from __future__ import annotations

import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def test_codex_goal_boundary_contract_is_codex_native_not_plugin_command():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    skill = (PLUGIN_ROOT / "skills" / "codexscientist-codex" / "SKILL.md").read_text(encoding="utf-8")
    combined = json.dumps(manifest, ensure_ascii=False) + "\n" + skill

    assert "/goal is Codex-native" in combined or "`/goal` is Codex-native" in combined
    assert "does not implement slash commands" in combined
    assert "MCP-only default" in combined
    assert "scripts/csctl.py" not in combined
    assert "CLI fallback" not in combined
    forbidden = [
        "CodexScientist implements /goal",
        "plugin command /goal",
        "registers /goal",
        "intercepts /goal",
        "simulates /goal",
    ]
    assert not any(item in combined for item in forbidden)
