from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_context_pack_service_writes_bounded_fixed_sections(tmp_path: Path):
    from kvasir_agent.services.context_pack import ContextPackService
    from kvasir_agent.services.frontier import FrontierService
    from kvasir_agent.services.manifest import ManifestService
    from kvasir_agent.services.project_state import ProjectLayout
    from kvasir_agent.services.queue import QueueService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = ManifestService(layout)
    manifest.write(manifest.default_manifest(name="Demo", goal="Improve"))
    QueueService(layout).submit(job_id="job1", command="python train.py")
    FrontierService(layout).add_candidate("I1", score=0.9, source="human", title="Compact idea")

    result = ContextPackService(layout).write_context_pack(max_chars=500)

    assert result["ok"] is True
    assert result["chars"] <= 500
    assert Path(result["path"]).read_text(encoding="utf-8") == result["content"]
    for section in ["active_state", "quest_state", "recovery_anchor", "metric_frontier", "recent_events", "relevant_negative_memory", "artifact_index", "log_digest", "budget_state"]:
        assert f"## {section}" in result["content"]


def test_context_pack_includes_latest_checkpoint_anchor(tmp_path: Path):
    from kvasir_agent.services.checkpoint import CheckpointService
    from kvasir_agent.services.context_pack import ContextPackService
    from kvasir_agent.services.manifest import ManifestService
    from kvasir_agent.services.project_state import ProjectLayout

    layout = ProjectLayout.from_project_root(tmp_path)
    ManifestService(layout).init(name="Demo", goal="Improve")
    checkpoint = CheckpointService(layout).create_checkpoint(
        phase="P3-2",
        completed=["resume"],
        decisions=[],
        validation=[],
        next_action="continue delta",
        artifact_refs=[],
        risk_flags=[],
    )

    result = ContextPackService(layout).write_context_pack(max_chars=1000)

    assert result["ok"] is True
    assert "## last_checkpoint" in result["content"]
    assert checkpoint["checkpoint_id"] in result["content"]
    assert "continue delta" in result["content"]
