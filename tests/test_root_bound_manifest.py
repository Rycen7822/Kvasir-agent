from __future__ import annotations

import json
from pathlib import Path

import yaml

from kvasir_agent.services.manifest import ManifestService
from kvasir_agent.services.project_state import ProjectLayout


def test_manifest_ensure_initialized_no_create_does_not_touch_fresh_project(tmp_path: Path) -> None:
    service = ManifestService(ProjectLayout.from_project_root(tmp_path))

    result = service.ensure_initialized(create=False)

    assert result["ok"] is False
    assert result["error_type"] == "no_research_state"
    assert not (tmp_path / "Kvasir-agent").exists()


def test_manifest_ensure_initialized_lazy_creates_root_bound_yaml_without_quests(tmp_path: Path) -> None:
    service = ManifestService(ProjectLayout.from_project_root(tmp_path))

    result = service.ensure_initialized(create=True, inferred_goal="root-bound goal", write_reason="test")

    assert result["ok"] is True
    manifest_path = tmp_path / "Kvasir-agent" / "research.yaml"
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
    assert not (tmp_path / "Kvasir-agent" / "quests").exists()
    events = (tmp_path / "Kvasir-agent" / "events" / "events.jsonl").read_text(encoding="utf-8")
    assert "research.initialized" in events


def test_manifest_reads_json_compatible_yaml_without_rewriting(tmp_path: Path) -> None:
    state_root = tmp_path / "Kvasir-agent"
    state_root.mkdir()
    path = state_root / "research.yaml"
    path.write_text(json.dumps({"project": {"name": "old"}, "goal": {"title": "old goal"}, "state": {"schema_version": 1}}), encoding="utf-8")
    service = ManifestService(ProjectLayout.from_project_root(tmp_path))

    before = (path.read_bytes(), path.stat().st_mtime_ns)
    result = service.ensure_initialized(create=False)

    assert result["ok"] is True
    manifest = result["manifest"]
    assert manifest["schema_version"] == 2
    assert manifest["layout_mode"] == "root_bound"
    raw = path.read_text(encoding="utf-8")
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert yaml.safe_load(raw)["project"]["name"] == "old"


def test_manifest_quest_identity_uses_root_manifest_not_path_routing(tmp_path: Path) -> None:
    service = ManifestService(ProjectLayout.from_project_root(tmp_path))
    created = service.ensure_initialized(create=True, inferred_goal="identity")

    identity = service.quest_identity(create=False)

    assert identity == {
        "ok": True,
        "quest_id": created["manifest"]["quest"]["id"],
        "quest_root": str(tmp_path / "Kvasir-agent"),
        "project_root": str(tmp_path.resolve()),
        "layout_mode": "root_bound",
    }
