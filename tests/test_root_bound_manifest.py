from __future__ import annotations

import json
from pathlib import Path

import yaml

from codex_scientist.services.manifest import ManifestService
from codex_scientist.services.project_state import ProjectLayout


def test_manifest_ensure_initialized_no_create_does_not_touch_fresh_project(tmp_path: Path) -> None:
    service = ManifestService(ProjectLayout.from_project_root(tmp_path))

    result = service.ensure_initialized(create=False)

    assert result["ok"] is False
    assert result["error_type"] == "no_research_state"
    assert not (tmp_path / "CodexScientist").exists()


def test_manifest_ensure_initialized_lazy_creates_root_bound_yaml_without_quests(tmp_path: Path) -> None:
    service = ManifestService(ProjectLayout.from_project_root(tmp_path))

    result = service.ensure_initialized(create=True, inferred_goal="root-bound goal", write_reason="test")

    assert result["ok"] is True
    manifest_path = tmp_path / "CodexScientist" / "research.yaml"
    assert manifest_path.exists()
    raw = manifest_path.read_text(encoding="utf-8")
    assert raw.lstrip().startswith("schema_version: 2")
    assert not raw.lstrip().startswith("{")
    manifest = yaml.safe_load(raw)
    assert manifest["schema_version"] == 2
    assert manifest["layout_mode"] == "root_bound"
    assert manifest["project"]["root"] == str(tmp_path.resolve())
    assert manifest["quest"]["root_bound"] is True
    assert manifest["quest"]["id"].startswith("qst_")
    assert manifest["goal"]["title"] == "root-bound goal"
    assert not (tmp_path / "CodexScientist" / "quests").exists()
    events = (tmp_path / "CodexScientist" / "events" / "events.jsonl").read_text(encoding="utf-8")
    assert "research.initialized" in events


def test_manifest_reads_json_compatible_yaml_and_rewrites_to_real_yaml(tmp_path: Path) -> None:
    state_root = tmp_path / "CodexScientist"
    state_root.mkdir()
    path = state_root / "research.yaml"
    path.write_text(json.dumps({"project": {"name": "old"}, "goal": {"title": "old goal"}, "state": {"schema_version": 1}}), encoding="utf-8")
    service = ManifestService(ProjectLayout.from_project_root(tmp_path))

    result = service.ensure_initialized(create=True, write_reason="upgrade")

    assert result["ok"] is True
    manifest = result["manifest"]
    assert manifest["schema_version"] == 2
    assert manifest["layout_mode"] == "root_bound"
    raw = path.read_text(encoding="utf-8")
    assert raw.lstrip().startswith("schema_version: 2")
    assert yaml.safe_load(raw)["project"]["name"] == "old"


def test_manifest_quest_identity_uses_root_manifest_not_path_routing(tmp_path: Path) -> None:
    service = ManifestService(ProjectLayout.from_project_root(tmp_path))
    created = service.ensure_initialized(create=True, inferred_goal="identity")

    identity = service.quest_identity(create=False)

    assert identity == {
        "ok": True,
        "quest_id": created["manifest"]["quest"]["id"],
        "quest_root": str(tmp_path / "CodexScientist"),
        "project_root": str(tmp_path.resolve()),
        "layout_mode": "root_bound",
    }
