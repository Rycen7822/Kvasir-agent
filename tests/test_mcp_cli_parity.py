from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_csctl(project: Path, *args: str) -> dict:
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


def test_mcp_manifest_validate_matches_cli_core_fields(tmp_path: Path):
    run_csctl(tmp_path, "manifest", "init", "--name", "demo", "--goal", "test goal")

    cli = run_csctl(tmp_path, "manifest", "validate")
    mcp = call_tool("cs_manifest_validate", {"project": str(tmp_path)})

    assert mcp["ok"] == cli["ok"]
    assert mcp["baseline_ready"] == cli["baseline_ready"]
    assert mcp["errors"] == cli["errors"]
    assert mcp["path"] == cli["path"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_queue_status_matches_cli_core_fields(tmp_path: Path):
    run_csctl(tmp_path, "queue", "submit", "--job-id", "job1", "--command", "python train.py")

    cli = run_csctl(tmp_path, "queue", "status")
    mcp = call_tool("cs_queue_status", {"project": str(tmp_path)})

    assert mcp["ok"] == cli["ok"]
    assert mcp["all_done"] == cli["all_done"]
    assert sorted(mcp["jobs"]) == sorted(cli["jobs"])
    assert mcp["jobs"]["job1"]["status"] == cli["jobs"]["job1"]["status"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_context_pack_matches_cli_core_fields(tmp_path: Path):
    run_csctl(tmp_path, "manifest", "init", "--name", "demo", "--goal", "test goal")

    cli = run_csctl(tmp_path, "summary", "context-pack", "--max-chars", "2000")
    mcp = call_tool("cs_context_pack", {"project": str(tmp_path), "max_chars": 2000})

    assert mcp["ok"] == cli["ok"]
    assert mcp["chars"] == cli["chars"]
    assert mcp["sha256"] == cli["sha256"]
    assert "## active_state" in mcp["content"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_trial_show_matches_cli_core_fields(tmp_path: Path):
    created = run_csctl(
        tmp_path,
        "trial",
        "propose",
        "--quest-id",
        "Q1",
        "--idea-id",
        "I1",
        "--hypothesis",
        "h",
        "--mechanism",
        "m",
    )
    trial_id = created["trial"]["trial_id"]

    cli = run_csctl(tmp_path, "trial", "show", trial_id)
    mcp = call_tool("cs_trial_show", {"project": str(tmp_path), "trial_id": trial_id})

    assert mcp["ok"] == cli["ok"]
    assert mcp["trial"]["trial_id"] == cli["trial"]["trial_id"]
    assert mcp["trial"]["status"] == cli["trial"]["status"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_wiki_query_pack_matches_cli_core_fields(tmp_path: Path):
    run_csctl(tmp_path, "wiki", "add-paper", "--paper-id", "P1", "--title", "Paper", "--summary", "Summary")
    run_csctl(tmp_path, "wiki", "add-idea", "--idea-id", "I1", "--title", "Idea", "--mechanism", "Mechanism")

    cli = run_csctl(tmp_path, "wiki", "query-pack", "--max-chars", "500")
    mcp = call_tool("cs_wiki_query_pack", {"project": str(tmp_path), "max_chars": 500})

    assert mcp["ok"] == cli["ok"]
    assert mcp["content"] == cli["content"]
    assert mcp["truncated"] == cli["truncated"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_review_status_matches_cli_core_fields(tmp_path: Path):
    run_csctl(
        tmp_path,
        "review",
        "create",
        "--claim-text",
        "claim",
        "--trial-id",
        "T0001",
        "--artifact-path",
        "artifact.txt",
        "--verdict",
        "pass",
        "--notes",
        "ok",
    )

    cli = run_csctl(tmp_path, "review", "status")
    mcp = call_tool("cs_review_status", {"project": str(tmp_path)})

    assert mcp["ok"] == cli["ok"]
    assert mcp["count"] == cli["count"]
    assert mcp["reviews"][0]["verdict"] == cli["reviews"][0]["verdict"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_cost_status_matches_cli_core_fields(tmp_path: Path):
    run_csctl(
        tmp_path,
        "cost",
        "check",
        "--action-class",
        "gpu cloud",
        "--estimated-cost-usd",
        "2.0",
        "--daily-cap-usd",
        "10.0",
    )

    cli = run_csctl(tmp_path, "cost", "status")
    mcp = call_tool("cs_cost_status", {"project": str(tmp_path), "daily_cap_usd": 10.0})

    assert mcp["ok"] == cli["ok"]
    assert mcp["decision"] == cli["decision"]
    assert mcp["requires_approval"] == cli["requires_approval"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_runner_status_matches_cli_core_fields(tmp_path: Path):
    started = run_csctl(tmp_path, "runner", "start", "--command", "python train.py", "--dry-run")
    run_id = started["run"]["run_id"]

    cli = run_csctl(tmp_path, "runner", "status", run_id)
    mcp = call_tool("cs_runner_status", {"project": str(tmp_path), "run_id": run_id})

    assert mcp["ok"] == cli["ok"]
    assert mcp["run"]["run_id"] == cli["run"]["run_id"]
    assert mcp["run"]["status"] == cli["run"]["status"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_queue_reconcile_matches_cli_core_fields(tmp_path: Path):
    run_csctl(tmp_path, "queue", "submit", "--job-id", "job1", "--command", "python train.py")
    run_csctl(tmp_path, "queue", "lease-next", "--worker-id", "w1", "--ttl-seconds", "0")

    cli = run_csctl(tmp_path, "queue", "reconcile")
    mcp = call_tool("cs_queue_reconcile", {"project": str(tmp_path)})

    assert mcp["ok"] == cli["ok"]
    assert mcp["jobs"]["job1"]["status"] == cli["jobs"]["job1"]["status"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_soak_accelerated_matches_cli_core_fields(tmp_path: Path):
    cli = run_csctl(tmp_path, "soak", "accelerated", "--days", "10", "--inject-failures")
    mcp = call_tool("cs_soak_accelerated", {"project": str(tmp_path), "days": 10, "inject_failures": True})

    assert mcp["ok"] == cli["ok"]
    assert mcp["accelerated"]["equivalent_days"] == cli["accelerated"]["equivalent_days"]
    assert mcp["wall_clock"]["verdict"] == "not_run"
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True


def test_mcp_soak_crash_resume_matches_cli_core_fields(tmp_path: Path):
    run_csctl(tmp_path, "queue", "submit", "--job-id", "job1", "--command", "python train.py")
    run_csctl(tmp_path, "queue", "lease-next", "--worker-id", "w1", "--ttl-seconds", "0")

    cli = run_csctl(tmp_path, "soak", "crash-resume", "--restart-label", "mcp-test")
    mcp = call_tool("cs_soak_crash_resume", {"project": str(tmp_path), "restart_label": "mcp-test"})

    assert mcp["ok"] == cli["ok"]
    assert mcp["restart_label"] == cli["restart_label"]
    assert mcp["queue"]["jobs"]["job1"]["status"] == cli["queue"]["jobs"]["job1"]["status"]
    assert mcp["transport"] == "codexscientist-mcp"
    assert mcp["mcp"] is True
