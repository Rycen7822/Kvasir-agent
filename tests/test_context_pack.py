from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_context_pack_service_writes_bounded_fixed_sections(tmp_path: Path):
    from codex_scientist.services.context_pack import ContextPackService
    from codex_scientist.services.frontier import FrontierService
    from codex_scientist.services.manifest import ManifestService
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.queue import QueueService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = ManifestService(layout)
    manifest.write(manifest.default_manifest(name="Demo", goal="Improve"))
    QueueService(layout).submit(job_id="job1", command="python train.py")
    FrontierService(layout).add_candidate("I1", score=0.9, source="human", title="Compact idea")

    result = ContextPackService(layout).write_context_pack(max_chars=500)

    assert result["ok"] is True
    assert result["chars"] <= 500
    assert Path(result["path"]).read_text(encoding="utf-8") == result["content"]
    for section in ["active_state", "next_action", "metric_frontier", "recent_events", "relevant_negative_memory", "artifact_index", "log_digest", "budget_state"]:
        assert f"## {section}" in result["content"]


def run_csctl(*args: str, project_root: Path) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "csctl.py"), "--project-root", str(project_root), *args],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_context_pack_cli_returns_path_digest_and_compact_content(tmp_path: Path):
    run_csctl("manifest", "init", "--name", "Demo", "--goal", "Improve", "--format", "json", project_root=tmp_path)

    result = run_csctl("summary", "context-pack", "--max-chars", "400", "--format", "json", project_root=tmp_path)

    assert result["ok"] is True
    assert result["chars"] <= 400
    assert result["sha256"]
    assert result["path"].endswith("DeepScientist/summaries/context_pack.md")
    assert "## active_state" in result["content"]
