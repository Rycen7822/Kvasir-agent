from __future__ import annotations

import json
from pathlib import Path


def test_migrate_legacy_quest_creates_manifest_and_report_without_deleting_source(tmp_path: Path):
    legacy = tmp_path / "CodexScientist" / "quests" / "legacy-001"
    legacy.mkdir(parents=True)
    (legacy / "quest.yaml").write_text("title: Legacy Quest\ngoal: Improve method\nmode: copilot\n", encoding="utf-8")
    (legacy / "notes.md").write_text("important legacy note", encoding="utf-8")

    from codex_scientist.services.migrations import MigrationService
    from codex_scientist.services.project_state import ProjectLayout

    result = MigrationService(ProjectLayout.from_project_root(tmp_path)).migrate_legacy_quests()

    assert result["ok"] is True
    assert result["migrated_count"] == 1
    assert (tmp_path / "CodexScientist" / "research.yaml").exists()
    assert (legacy / "quest.yaml").exists(), "migration must not delete legacy source"
    report = json.loads((tmp_path / "CodexScientist" / "migrations" / "migration_report.json").read_text(encoding="utf-8"))
    assert report["items"][0]["quest_id"] == "legacy-001"
    assert report["items"][0]["source_preserved"] is True
