from __future__ import annotations

from kvasir_agent.mcp.tool_registry import call_tool
from kvasir_agent.services.manifest import ManifestService
from kvasir_agent.services.project_state import ProjectLayout


def _legacy_quest(root, quest_id: str) -> None:
    legacy = root / "Kvasir-agent" / "quests" / quest_id
    legacy.mkdir(parents=True)
    (legacy / "quest.yaml").write_text(f"quest_id: {quest_id}\ntitle: {quest_id}\n", encoding="utf-8")


def test_ka_status_fresh_project_is_read_only_no_research_state(tmp_path):
    payload = call_tool("ka_status", {"project": str(tmp_path)})

    assert payload["ok"] is True
    assert payload["research_state"] == "no_research_state"
    assert payload["legacy_status"] == "none"
    assert payload["state_root_exists"] is False
    assert not (tmp_path / "Kvasir-agent").exists()


def test_ka_status_reports_manifest_summary_without_legacy_routing(tmp_path):
    created = ManifestService(ProjectLayout.from_project_root(tmp_path)).ensure_initialized(create=True, inferred_goal="status goal")

    payload = call_tool("ka_status", {"project": str(tmp_path)})

    assert payload["ok"] is True
    assert payload["research_state"] == "ready"
    assert payload["quest_id"] == created["manifest"]["quest"]["id"]
    assert payload["quest_root"] == str(tmp_path / "Kvasir-agent")
    assert payload["manifest"]["goal"] == "status goal"


def test_ka_status_detects_single_legacy_quest_without_importing(tmp_path):
    _legacy_quest(tmp_path, "QLEGACY")

    payload = call_tool("ka_status", {"project": str(tmp_path)})

    assert payload["ok"] is True
    assert payload["research_state"] == "single_legacy_detected"
    assert payload["legacy_status"] == "single_legacy_detected"
    assert payload["legacy_quest_ids"] == ["QLEGACY"]
    assert not (tmp_path / "Kvasir-agent" / "research.yaml").exists()


def test_ka_status_blocks_multiple_legacy_quests_without_latest_fallback(tmp_path):
    for quest_id in ("Q1", "Q2"):
        _legacy_quest(tmp_path, quest_id)

    payload = call_tool("ka_status", {"project": str(tmp_path)})

    assert payload["ok"] is True
    assert payload["research_state"] == "multiple_legacy_quests_blocked"
    assert payload["legacy_status"] == "multiple_legacy_quests_blocked"
    assert payload["legacy_quest_ids"] == ["Q1", "Q2"]
    assert "quest_id" not in payload
