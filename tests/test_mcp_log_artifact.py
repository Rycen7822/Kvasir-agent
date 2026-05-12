from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run_csctl(project: Path, *args: str) -> dict:
    completed = subprocess.run(
        [
            PYTHON,
            str(PLUGIN_ROOT / "scripts" / "csctl.py"),
            "--project-root",
            str(project),
            "--format",
            "json",
            *args,
        ],
        cwd=PLUGIN_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(completed.stdout)


def test_p3_log_and_artifact_tools_are_registered():
    names = {tool["name"] for tool in tools_list_payload()["tools"]}

    assert {"cs_log_digest", "cs_artifact_index"} <= names
    assert len(names) == 20


def test_mcp_log_digest_and_artifact_index_match_cli_core_fields(tmp_path: Path):
    started = _run_csctl(tmp_path, "runner", "start", "--command", "python train.py", "--dry-run")
    run_id = started["run"]["run_id"]
    log_path = Path(started["run"]["log_path"])
    log_path.write_text("RuntimeError: failed token=" + "supersecret", encoding="utf-8")
    artifact_dir = tmp_path / "CodexScientist" / "artifacts"
    artifact_dir.mkdir(parents=True)
    artifact = artifact_dir / "result.txt"
    artifact.write_text("large artifact body", encoding="utf-8")

    cli_log = _run_csctl(tmp_path, "runner", "log-digest", run_id, "--max-tail-lines", "5")
    mcp_log = call_tool("cs_log_digest", {"project": str(tmp_path), "run_id": run_id, "max_tail_lines": 5})
    assert mcp_log["ok"] == cli_log["ok"]
    assert mcp_log["run_id"] == cli_log["run_id"]
    assert mcp_log["sha256"] == cli_log["sha256"]
    assert "supersecret" not in json.dumps(mcp_log, ensure_ascii=False)

    cli_artifacts = _run_csctl(tmp_path, "summary", "artifact-index", "--max-items", "10")
    mcp_artifacts = call_tool("cs_artifact_index", {"project": str(tmp_path), "max_items": 10})
    assert mcp_artifacts["ok"] == cli_artifacts["ok"]
    assert mcp_artifacts["count"] == cli_artifacts["count"] == 1
    assert mcp_artifacts["artifacts"][0]["sha256"] == cli_artifacts["artifacts"][0]["sha256"]
    assert "large artifact body" not in json.dumps(mcp_artifacts, ensure_ascii=False)
