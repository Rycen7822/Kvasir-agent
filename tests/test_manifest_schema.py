from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_manifest_validation_rejects_missing_primary_metric(tmp_path: Path):
    from kvasir_agent.services.manifest import ManifestService
    from kvasir_agent.services.project_state import ProjectLayout

    service = ManifestService(ProjectLayout.from_project_root(tmp_path))
    manifest = service.default_manifest(name="Bad", goal="Missing metric")
    manifest["metrics"].pop("primary")
    service.write(manifest)

    result = service.validate()
    assert result["ok"] is False
    assert "metrics.primary" in result["errors"]
