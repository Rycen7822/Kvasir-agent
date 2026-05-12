from __future__ import annotations

from pathlib import Path

from codex_scientist.services.artifacts import ArtifactIndexService
from codex_scientist.services.project_state import ProjectLayout


def test_artifact_index_returns_refs_hashes_and_no_file_content(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    artifact_dir = layout.state_root / "artifacts"
    artifact_dir.mkdir(parents=True)
    artifact = artifact_dir / "metrics.json"
    artifact.write_text('{"accuracy": 0.9, "token": "supersecret"}', encoding="utf-8")

    result = ArtifactIndexService(layout).index(max_items=10)

    assert result["ok"] is True
    assert result["count"] == 1
    item = result["artifacts"][0]
    assert item["path"] == str(artifact)
    assert item["type"] == "json"
    assert item["bytes"] == artifact.stat().st_size
    assert len(item["sha256"]) == 64
    assert "content" not in item
    assert "supersecret" not in str(result)


def test_artifact_index_truncated_only_when_more_items_exist(tmp_path: Path):
    layout = ProjectLayout.from_project_root(tmp_path)
    artifact_dir = layout.state_root / "artifacts"
    artifact_dir.mkdir(parents=True)
    for name in ("a.txt", "b.txt"):
        (artifact_dir / name).write_text(name, encoding="utf-8")

    exact = ArtifactIndexService(layout).index(max_items=2)
    limited = ArtifactIndexService(layout).index(max_items=1)

    assert exact["count"] == 2
    assert exact["truncated"] is False
    assert limited["count"] == 1
    assert limited["truncated"] is True
