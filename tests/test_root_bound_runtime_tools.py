from __future__ import annotations

import json
from pathlib import Path

from kvasir_agent.runtime import tools
from kvasir_agent.runtime.config import NativeConfig
from kvasir_agent.runtime.state import StateStore


def _payload(raw: str) -> dict:
    data = json.loads(raw)
    assert data.get("ok") is True, data
    return data


def test_runtime_tools_do_not_reintroduce_active_or_latest_quest_routing():
    source = Path(tools.__file__).read_text(encoding="utf-8")

    forbidden = [
        "_active_or_latest_quest_id",
        "active quest",
        "latest quest",
        "list_quests()",
    ]
    for token in forbidden:
        assert token not in source


def test_state_store_root_bound_session_does_not_persist_active_quest_id(tmp_path: Path):
    config = NativeConfig(
        config_root=tmp_path / "Kvasir-agent",
        config_path=tmp_path / "Kvasir-agent" / "config" / "codex-native.yaml",
        runtime_home=tmp_path / "Kvasir-agent",
        session_map_path=tmp_path / "sessions.json",
    )
    store = StateStore(config)

    state = store.set_active_quest("QOLD", "s1", active_stage="experiment", project_root=str(tmp_path))

    assert "active_quest_id" not in state
    assert state["project_root"] == str(tmp_path)
    assert state["active_stage"] == "experiment"
    assert store.active_quest_id("s1") is None
    assert store.legacy_active_quest_id("s1") is None


def test_native_new_quest_initializes_root_manifest_without_legacy_quest_dir(tmp_path: Path):
    payload = _payload(tools.ka_new_quest({"project": str(tmp_path), "goal": "root goal", "title": "Root Goal"}))

    assert payload["deprecated_lifecycle_tool"] is True
    assert payload["root_bound_alias"] == "research_manifest_initialized"
    assert payload["quest_root"] == str(tmp_path / "Kvasir-agent")
    assert (tmp_path / "Kvasir-agent" / "research.yaml").exists()
    assert not (tmp_path / "Kvasir-agent" / "quests").exists()


def test_native_new_quest_accepts_supplied_quest_id_as_initial_provenance_only(tmp_path: Path):
    payload = _payload(tools.ka_new_quest({"project": str(tmp_path), "goal": "root goal", "quest_id": "root-provenance"}))

    assert payload["quest_id"] == "root-provenance"
    assert payload["quest_root"] == str(tmp_path / "Kvasir-agent")
    assert (tmp_path / "Kvasir-agent" / "research.yaml").exists()
    assert not (tmp_path / "Kvasir-agent" / "quests" / "root-provenance").exists()


def test_native_artifact_record_without_quest_id_uses_root_bound_vendor_shim(tmp_path: Path):
    payload = _payload(
        tools.ka_artifact_record(
            {
                "project": str(tmp_path),
                "kind": "report",
                "summary": "root artifact",
                "payload": {"kind": "report", "summary": "root artifact"},
            }
        )
    )

    state_root = tmp_path / "Kvasir-agent"
    assert payload["quest_root"] == str(state_root)
    assert (state_root / "quest.yaml").exists()
    assert (state_root / ".ka").is_dir()
    assert not (state_root / "quests").exists()
    artifact = payload["artifact"]
    path_text = json.dumps(artifact, ensure_ascii=False)
    assert str(state_root) in path_text
    assert "/quests/" not in path_text


def test_supplied_mismatched_quest_id_is_rejected_without_path_switch(tmp_path: Path):
    created = _payload(tools.ka_new_quest({"project": str(tmp_path), "goal": "root goal"}))
    manifest_quest_id = created["quest_id"]

    raw = json.loads(
        tools.ka_artifact_record(
            {
                "project": str(tmp_path),
                "quest_id": manifest_quest_id + "_other",
                "kind": "report",
                "summary": "bad",
                "payload": {"kind": "report", "summary": "bad"},
            }
        )
    )

    assert raw["ok"] is False
    assert raw["error_type"] == "root_bound_quest_id_mismatch"
    assert raw["manifest_quest_id"] == manifest_quest_id
    assert raw["state_root"] == str(tmp_path / "Kvasir-agent")
    assert not (tmp_path / "Kvasir-agent" / "quests" / f"{manifest_quest_id}_other").exists()
