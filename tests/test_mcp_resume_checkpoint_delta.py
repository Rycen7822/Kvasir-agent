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


def test_p3_resume_checkpoint_delta_tools_are_registered():
    names = {tool["name"] for tool in tools_list_payload()["tools"]}

    assert {"cs_resume_brief", "cs_checkpoint", "cs_pack_delta"} <= names
    assert len(names) >= 18


def test_mcp_checkpoint_resume_and_delta_core_flow_matches_cli(tmp_path: Path):
    _run_csctl(tmp_path, "manifest", "init", "--name", "demo", "--goal", "resume goal")

    cli_checkpoint = _run_csctl(
        tmp_path,
        "summary",
        "checkpoint",
        "--phase",
        "P3-2",
        "--completed",
        "cli checkpoint",
        "--decision",
        "use compact state",
        "--validation",
        "pytest",
        "--next-action",
        "call resume brief",
        "--artifact-ref",
        "artifact.json",
        "--risk-flag",
        "none",
    )
    mcp_checkpoint = call_tool(
        "cs_checkpoint",
        {
            "project": str(tmp_path),
            "phase": "P3-2b",
            "completed": ["mcp checkpoint"],
            "decisions": ["use MCP"],
            "validation": ["pytest"],
            "next_action": "call delta",
            "artifact_refs": ["artifact2.json"],
            "risk_flags": [],
        },
    )

    assert cli_checkpoint["ok"] is True
    assert mcp_checkpoint["ok"] is True
    assert len(cli_checkpoint["sha256"]) == 64
    assert len(mcp_checkpoint["sha256"]) == 64

    cli_resume = _run_csctl(tmp_path, "summary", "resume-brief", "--max-chars", "4000")
    mcp_resume = call_tool("cs_resume_brief", {"project": str(tmp_path), "max_chars": 4000})

    assert mcp_resume["ok"] == cli_resume["ok"]
    assert mcp_resume["goal"]["title"] == cli_resume["goal"]["title"] == "resume goal"
    assert mcp_resume["last_checkpoint"]["checkpoint_id"] == cli_resume["last_checkpoint"]["checkpoint_id"]
    assert mcp_resume["autonomy_mode"] == "copilot"

    cli_delta = _run_csctl(
        tmp_path,
        "summary",
        "pack-delta",
        "--since-checkpoint-id",
        cli_checkpoint["checkpoint_id"],
        "--max-chars",
        "4000",
    )
    mcp_delta = call_tool(
        "cs_pack_delta",
        {
            "project": str(tmp_path),
            "since_checkpoint_id": cli_checkpoint["checkpoint_id"],
            "max_chars": 4000,
        },
    )

    assert mcp_delta["ok"] == cli_delta["ok"]
    assert mcp_delta["source_event_range"] == cli_delta["source_event_range"]
    assert mcp_delta["new_events_summary"] == cli_delta["new_events_summary"]
