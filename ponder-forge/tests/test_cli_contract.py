from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli.py"


def run_cli(tmp_path: Path, *args: str, input_text: str | None = None, expect_success: bool = True) -> dict:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(tmp_path / "hermes-home")
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        env=env,
        text=True,
        input=input_text,
        capture_output=True,
        check=False,
    )
    if expect_success:
        assert result.returncode == 0, result.stderr + result.stdout
    else:
        assert result.returncode != 0, result.stderr + result.stdout
    assert result.stdout.strip(), result.stderr
    return json.loads(result.stdout)


def test_cli_workflow_start_plan_report_verify_gate_finalize_and_late_reject(tmp_path):
    start = run_cli(tmp_path, "start", "--goal", "research source notes", "--profile", "auto")
    assert start["success"] is True
    assert start["profile"] == "research"
    assert start["next_command"] == "plan"

    plan = run_cli(tmp_path, "plan", "--run-id", start["run_id"])
    assert plan["success"] is True
    assert plan["profile"] == "research"
    first_task = plan["tasks"][0]

    delegations = run_cli(tmp_path, "delegations", "--run-id", start["run_id"])
    assert delegations["success"] is True
    assert delegations["native_tool_to_call_next"] == "delegate_task"
    assert delegations["delegate_task_payload"]["tasks"]

    report_path = tmp_path / "producer_report.json"
    report_path.write_text(
        json.dumps(
            {
                "run_id": start["run_id"],
                "task_id": first_task["task_id"],
                "role": first_task["role"],
                "summary": "source-backed fact",
                "assertions": [
                    {
                        "assertion_type": "factual_claim",
                        "text": "Ponder-Forge can run as a CLI-backed skill workflow.",
                        "importance": 0.95,
                        "critical": True,
                        "evidence": [
                            {
                                "evidence_type": "source_quote",
                                "source_ref": "worknotes/2026-07-04-skill-pure-cli-implementation-plan.md",
                                "quote_or_observation": "Add a stdlib cli.py that calls existing core modules directly and emits JSON.",
                                "directness": 0.95,
                            }
                        ],
                    }
                ],
                "artifacts": [
                    {
                        "artifact_type": "implementation_plan",
                        "path": "worknotes/2026-07-04-skill-pure-cli-implementation-plan.md",
                        "summary": "CLI conversion plan",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = run_cli(tmp_path, "submit-report", "--file", str(report_path))
    assert report["success"] is True
    assertion_id = report["assertion_ids"][0]

    review = run_cli(tmp_path, "verify", "--run-id", start["run_id"], "--mode", "independent_review", "--target-id", assertion_id)
    reviewer_task = review["reviewer_tasks"][0]
    verdict = run_cli(
        tmp_path,
        "verify",
        "--run-id",
        start["run_id"],
        "--mode",
        "independent_review",
        "--target-id",
        assertion_id,
        "--reviewer-task-id",
        reviewer_task["task_id"],
        "--reviewer-role",
        reviewer_task["role"],
        "--independent-from-task-id",
        first_task["task_id"],
        "--verdict",
        "accept",
        "--confidence",
        "0.9",
        "--rationale",
        "fixture accepts the CLI-backed workflow claim",
    )
    assert verdict["success"] is True
    assert verdict["final_verdict"] is True

    gate = run_cli(tmp_path, "gate", "--run-id", start["run_id"])
    assert gate["success"] is True
    assert gate["status"] == "passed"
    assert gate["metrics"]["independent_review_coverage"] == 1.0

    final = run_cli(tmp_path, "finalize", "--run-id", start["run_id"])
    assert final["success"] is True
    assert final["status"] == "final"
    assert "CLI-backed skill workflow" in final["final_report_markdown"]

    late_path = tmp_path / "late_report.json"
    late_path.write_text(
        json.dumps(
            {
                "run_id": start["run_id"],
                "task_id": first_task["task_id"],
                "role": first_task["role"],
                "summary": "late report",
                "assertions": [
                    {
                        "assertion_type": "factual_claim",
                        "text": "late report should be rejected",
                        "critical": True,
                        "evidence": [{"evidence_type": "source_quote", "source_ref": "late.md"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    late = run_cli(tmp_path, "submit-report", "--file", str(late_path), expect_success=False)
    assert late["success"] is False
    assert "completed" in late["error"]

    status = run_cli(tmp_path, "status", "--run-id", start["run_id"])
    assert status["counts"]["reports"] == 1
    assert status["gate_status"] == "passed"


def test_cli_submit_report_accepts_stdin(tmp_path):
    start = run_cli(tmp_path, "start", "--goal", "research source notes")
    plan = run_cli(tmp_path, "plan", "--run-id", start["run_id"])
    task = plan["tasks"][0]
    payload = {
        "run_id": start["run_id"],
        "task_id": task["task_id"],
        "role": task["role"],
        "summary": "stdin report",
        "assertions": [],
    }

    submitted = run_cli(tmp_path, "submit-report", "--file", "-", input_text=json.dumps(payload))

    assert submitted["success"] is True
    assert submitted["report_id"].startswith("pf_report_")
