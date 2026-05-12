from __future__ import annotations

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def test_main_skill_declares_default_copilot_and_autonomous_idea_gate():
    text = (PLUGIN_ROOT / "skills" / "codexscientist-codex" / "SKILL.md").read_text(encoding="utf-8")

    required = [
        "default mode is `copilot`",
        "autonomous_idea_improvement",
        "only when the user explicitly asks",
        "manifest or handoff explicitly requires autonomous idea improvement",
        "do not invent or improve ideas automatically",
    ]
    for phrase in required:
        assert phrase in text


def test_main_skill_remains_low_token_router_not_full_tool_manual():
    text = (PLUGIN_ROOT / "skills" / "codexscientist-codex" / "SKILL.md").read_text(encoding="utf-8")

    assert len(text) < 9000
    assert text.count("cs_") < 35
    assert "48 public" not in text.lower()
    assert "48-tool" not in text.lower()


def test_architecture_doc_freezes_plugin_service_adapter_boundaries():
    text = (PLUGIN_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")

    for phrase in [
        "Codex-Scientist is a Codex CLI plugin",
        "stable curated MCP",
        "CLI fallback",
        "default mode is `copilot`",
        "scripts/csctl.py",
        "scripts/cs_mcp.py",
        "codex_scientist/services",
        "codex_scientist/adapters",
        "CodexScientist/",
        "Codex-native operation layer",
        "CodexScientist semantic/provenance layer",
    ]:
        assert phrase in text


def test_main_skill_and_docs_no_longer_claim_no_mcp_final_contract():
    paths = [
        PLUGIN_ROOT / "skills" / "codexscientist-codex" / "SKILL.md",
        PLUGIN_ROOT / "docs" / "ARCHITECTURE.md",
        PLUGIN_ROOT / "docs" / "USAGE.md",
        PLUGIN_ROOT / "docs" / "INSTALL.md",
    ]
    forbidden = ["Do not use " + "MCP for this plugin", "not " + "MCP", "No-" + "MCP contract", "mcp" + "=false"]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "stable curated MCP" in text
        assert "CLI fallback" in text
        for phrase in forbidden:
            assert phrase not in text
