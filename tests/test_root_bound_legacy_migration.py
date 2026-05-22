from __future__ import annotations

import json
from pathlib import Path

import yaml

from codex_scientist.mcp.tool_registry import call_tool
from codex_scientist.services.legacy_migration import LegacyQuestDetector
from codex_scientist.services.manifest import ManifestService
from codex_scientist.services.project_state import ProjectLayout


def _legacy_quest(root: Path, quest_id: str, *, title: str | None = None, fmt: str = "yaml") -> Path:
    quest_root = root / "CodexScientist" / "quests" / quest_id
    quest_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "quest_id": quest_id,
        "title": title or quest_id,
        "goal": {"title": title or f"Goal {quest_id}"},
        "updated_at": f"2026-01-0{len(quest_id) % 9 + 1}T00:00:00Z",
    }
    if fmt == "json":
        (quest_root / "quest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        (quest_root / "quest.yaml").write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return quest_root


def test_legacy_detector_scans_only_quest_yaml_or_json(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    q1 = _legacy_quest(tmp_path, "Q1", title="First legacy")
    _legacy_quest(tmp_path, "Q2", title="Second legacy", fmt="json")
    ignored = tmp_path / "CodexScientist" / "quests" / "empty-dir"
    ignored.mkdir(parents=True)
    (tmp_path / "CodexScientist" / "session_map.json").write_text(json.dumps({"active_quest_id": "SHOULD_NOT_COUNT"}), encoding="utf-8")

    status = LegacyQuestDetector.inspect(layout)

    assert status.status == "multiple_legacy_quests_blocked"
    assert [quest.quest_id for quest in status.quests] == ["Q1", "Q2"]
    assert status.quests[0].title == "First legacy"
    assert status.quests[0].path == q1


def test_single_legacy_quest_is_conservatively_imported_on_first_write(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    legacy_root = _legacy_quest(tmp_path, "QLEG", title="Legacy research")
    (legacy_root / "artifacts" / "metrics.json").parent.mkdir(parents=True, exist_ok=True)
    (legacy_root / "artifacts" / "metrics.json").write_text('{"score": 1}\n', encoding="utf-8")
    (legacy_root / "runtime" / "goal_state.json").parent.mkdir(parents=True, exist_ok=True)
    (legacy_root / "runtime" / "goal_state.json").write_text('{"stage": "analysis"}\n', encoding="utf-8")

    result = ManifestService(layout).ensure_initialized(create=True, inferred_goal="new durable write")

    assert result["ok"] is True
    assert result["created"] is True
    assert result["migrated"] is True
    manifest = yaml.safe_load((tmp_path / "CodexScientist" / "research.yaml").read_text(encoding="utf-8"))
    assert manifest["quest"]["id"] == "QLEG"
    assert manifest["goal"]["title"] == "Legacy research"
    assert manifest["legacy"]["migrated_from"] == "CodexScientist/quests/QLEG"
    assert manifest["legacy"]["source_preserved"] is True
    assert (tmp_path / "CodexScientist" / "artifacts" / "metrics.json").read_text(encoding="utf-8") == '{"score": 1}\n'
    assert (tmp_path / "CodexScientist" / "runtime" / "goal_state.json").exists()
    assert (legacy_root / "quest.yaml").exists()

    report = json.loads((tmp_path / "CodexScientist" / "migrations" / "root_bound_migration_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "imported"
    assert report["source"] == "CodexScientist/quests/QLEG"
    assert "artifacts/metrics.json" in report["imported_paths"]
    events = (tmp_path / "CodexScientist" / "events" / "events.jsonl").read_text(encoding="utf-8")
    assert "migration.root_bound_single_legacy_imported" in events


def test_single_legacy_import_records_invalid_quest_id_mapping_in_report(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    legacy_root = tmp_path / "CodexScientist" / "quests" / "legacy-dir"
    legacy_root.mkdir(parents=True)
    (legacy_root / "quest.yaml").write_text("quest_id: bad legacy/id!\ntitle: Legacy with bad id\n", encoding="utf-8")

    result = ManifestService(layout).ensure_initialized(create=True, inferred_goal="bad id")

    assert result["ok"] is True
    manifest = yaml.safe_load((tmp_path / "CodexScientist" / "research.yaml").read_text(encoding="utf-8"))
    assert manifest["quest"]["id"] == "qst_bad_legacy_id"
    report = json.loads((tmp_path / "CodexScientist" / "migrations" / "root_bound_migration_report.json").read_text(encoding="utf-8"))
    assert report["quest_id_mapping"] == {"from": "bad legacy/id!", "to": "qst_bad_legacy_id"}


def test_multiple_legacy_quests_block_status_and_first_write(tmp_path: Path):
    _legacy_quest(tmp_path, "QA", title="Alpha")
    _legacy_quest(tmp_path, "QB", title="Beta")

    status = call_tool("cs_status", {"project": str(tmp_path)})
    assert status["ok"] is True
    assert status["research_state"] == "multiple_legacy_quests_blocked"
    assert status["legacy_status"] == "multiple_legacy_quests_blocked"
    assert [quest["quest_id"] for quest in status["legacy_quests"]] == ["QA", "QB"]
    assert status["legacy_quests"][0]["title"] == "Alpha"

    write = call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "must block"})
    assert write["ok"] is False
    assert write["error_type"] == "multiple_legacy_quests_blocked"
    assert [quest["quest_id"] for quest in write["legacy_quests"]] == ["QA", "QB"]
    assert not (tmp_path / "CodexScientist" / "research.yaml").exists()


def test_single_legacy_import_reports_conflicts_without_overwriting(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    legacy_root = _legacy_quest(tmp_path, "QCONFLICT", title="Conflict legacy")
    (legacy_root / "artifacts").mkdir(parents=True, exist_ok=True)
    (legacy_root / "artifacts" / "same_name.txt").write_text("legacy\n", encoding="utf-8")
    destination = tmp_path / "CodexScientist" / "artifacts" / "same_name.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("root-bound existing\n", encoding="utf-8")

    result = ManifestService(layout).ensure_initialized(create=True, inferred_goal="conflict")

    assert result["ok"] is False
    assert result["error_type"] == "migration_conflict"
    assert destination.read_text(encoding="utf-8") == "root-bound existing\n"
    assert not (tmp_path / "CodexScientist" / "research.yaml").exists()
    conflicts = json.loads((tmp_path / "CodexScientist" / "migrations" / "root_bound_conflicts.json").read_text(encoding="utf-8"))
    assert conflicts["status"] == "blocked"
    assert conflicts["conflicts"][0]["relative_path"] == "artifacts/same_name.txt"
