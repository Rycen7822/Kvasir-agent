from __future__ import annotations

import json
from pathlib import Path

import yaml

from kvasir_agent.services.legacy_migration import LegacyQuestDetector
from kvasir_agent.services.manifest import ManifestService
from kvasir_agent.services.project_state import ProjectLayout


def _legacy_quest(root: Path, quest_id: str, *, title: str | None = None, fmt: str = "yaml") -> Path:
    quest_root = root / "Kvasir-agent" / "quests" / quest_id
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
    ignored = tmp_path / "Kvasir-agent" / "quests" / "empty-dir"
    ignored.mkdir(parents=True)
    (tmp_path / "Kvasir-agent" / "session_map.json").write_text(json.dumps({"active_quest_id": "SHOULD_NOT_COUNT"}), encoding="utf-8")

    status = LegacyQuestDetector.inspect(layout)

    assert status.status == "multiple_legacy_quests_blocked"
    assert [quest.quest_id for quest in status.quests] == ["Q1", "Q2"]
    assert status.quests[0].title == "First legacy"
    assert status.quests[0].path == q1
