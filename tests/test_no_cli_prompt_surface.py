from __future__ import annotations

import json
from pathlib import Path

from codex_scientist.mcp import surface_allowlist
from codex_scientist.mcp.skill_index import _filter_agent_facing_content, iter_skill_cards, load_skill
from codex_scientist.mcp.tool_registry import call_tool

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("scripts/csctl.py", "CLI fallback")
RUNTIME_FORBIDDEN = (
    "scripts/" + "csctl.py",
    "CLI " + "fallback",
    "cs" + "ctl services",
    "current " + "csctl surface",
    "`cs" + "ctl`",
    " " + "csctl ",
    "python scripts/" + "csctl.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_p4_terms_document_defines_goal_boundary_and_hidden_cli_plane():
    terms = ROOT / "docs" / "P4_TERMS.md"
    assert terms.exists(), "P4 terms must be durable and reviewable"
    text = _read(terms)

    required_terms = [
        "agent-facing surface",
        "hidden admin/debug CLI",
        "MCP-only default",
        "fail closed",
        "Codex-goal-driven research loop adapter",
        "quest root",
        "method improvement gate",
    ]
    for term in required_terms:
        assert term in text

    assert "`/goal` is Codex-native" in text
    assert "CodexScientist does not implement slash commands" in text


def test_default_agent_facing_surface_has_no_cli_fallback_language():
    violations = surface_allowlist.find_agent_facing_cli_violations(ROOT)
    assert violations == []


def test_plugin_manifest_default_prompt_is_mcp_only_and_codex_goal_bounded():
    manifest = json.loads(_read(ROOT / ".codex-plugin" / "plugin.json"))
    interface = manifest["interface"]
    fields = [
        manifest.get("description", ""),
        interface.get("shortDescription", ""),
        interface.get("longDescription", ""),
        "\n".join(interface.get("defaultPrompt", [])),
    ]
    combined = "\n".join(fields)

    for forbidden in FORBIDDEN:
        assert forbidden not in combined
    assert "MCP-only default" in combined
    assert "`/goal` is Codex-native" in combined
    assert "does not implement slash commands" in combined


def test_runtime_skill_load_filters_cli_fallback_from_default_view():
    payload = load_skill({"skill_id": "codexscientist-codex", "view": "runtime", "max_chars": 16000})
    assert payload["ok"] is True
    content = payload["content"]
    for forbidden in FORBIDDEN:
        assert forbidden not in content
    assert payload["view"] == "runtime"
    assert payload.get("agent_facing") is not False


def test_runtime_skill_load_filters_bare_csctl_from_all_agent_facing_skills():
    skill_ids = {card.skill_id for card in iter_skill_cards()}
    assert "codexscientist-writing-plans" in skill_ids
    assert "codexscientist-analysis-campaign" in skill_ids

    violations: list[tuple[str, str]] = []
    checked_contents: dict[str, str] = {}
    for skill_id in sorted(skill_ids):
        payload = load_skill({"skill_id": skill_id, "view": "runtime", "max_chars": 16000})
        assert payload["ok"] is True
        assert payload["view"] == "runtime"
        assert payload.get("agent_facing") is not False
        assert isinstance(payload.get("filtered_agent_facing_cli_terms"), list)
        content = payload["content"]
        checked_contents[skill_id] = content
        lowered = content.lower()
        for forbidden in RUNTIME_FORBIDDEN:
            if forbidden.lower() in lowered:
                violations.append((skill_id, forbidden))

    assert violations == []
    assert "MCP `cs_*` tools" in checked_contents["codexscientist-writing-plans"]
    assert "MCP `cs_*` tools" in checked_contents["codexscientist-analysis-campaign"]


def test_agent_facing_skill_filter_reports_filtered_cli_terms():
    content, terms = _filter_agent_facing_content(
        "Use scripts/" + "csctl.py for compatibility.\nKeep MCP cs_* tools in the runtime view."
    )

    assert "scripts/" + "csctl.py" not in content
    assert "MCP cs_* tools" in content
    assert "scripts/" + "csctl.py" in terms
    assert "cs" + "ctl" in terms


def test_mcp_missing_tool_fails_closed_without_cli_fallback_suggestion():
    payload = call_tool("cs_definitely_missing_for_p4", {})
    assert payload["ok"] is False
    assert payload["recoverable"] is True
    assert payload["error_type"] == "unknown_tool"
    combined = json.dumps(payload, ensure_ascii=False)
    for forbidden in FORBIDDEN:
        assert forbidden not in combined
    assert "Run cs_doctor" in combined or "tools/list" in combined
