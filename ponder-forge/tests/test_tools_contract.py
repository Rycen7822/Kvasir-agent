from __future__ import annotations

import json
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tools_module = _load_module("tools.py", "ponder_forge_tools_contract_test")
commands_module = _load_module("commands.py", "ponder_forge_commands_contract_test")
HANDLERS = tools_module.HANDLERS
start_ponder_forge_command = commands_module.start_ponder_forge_command


def _call(name: str, args: dict) -> dict:
    return json.loads(HANDLERS[name](args))


def test_public_tool_chain_start_plan_report_gate_finalize(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    start = _call("ponder_forge_start", {"goal": "research papers from my knowledge base", "profile": "auto"})
    assert start["success"] is True
    assert start["profile"] == "research"
    assert start["next_tool"] == "ponder_forge_plan"

    plan = _call("ponder_forge_plan", {"run_id": start["run_id"]})
    assert plan["success"] is True
    assert plan["profile"] == "research"
    assert plan["tasks"]
    first_task = plan["tasks"][0]

    report = _call(
        "ponder_forge_report_submit",
        {
            "run_id": start["run_id"],
            "task_id": first_task["task_id"],
            "role": first_task["role"],
            "summary": "found a supported fact",
            "assertions": [
                {
                    "assertion_type": "factual_claim",
                    "text": "Ponder-Forge uses profile-specific evidence",
                    "importance": 0.9,
                    "critical": True,
                    "evidence": [
                        {
                            "evidence_type": "source_quote",
                            "source_ref": "worknotes/ponder_forge_project_plan_v2.md",
                            "quote_or_observation": "不同 profile 的 evidence 类型不同",
                            "directness": 0.9,
                        }
                    ],
                }
            ],
            "artifacts": [
                {"artifact_type": "analysis_report", "path": "worknotes/final.md", "summary": "fixture report"}
            ],
        },
    )
    assert report["success"] is True
    assert len(report["assertion_ids"]) == 1

    pool = _call("ponder_forge_pool_status", {"run_id": start["run_id"]})
    assert pool["success"] is True
    assert pool["counts"]["reports"] == 1
    assert pool["counts"]["assertions"] == 1

    review = _call("ponder_forge_verify", {"run_id": start["run_id"], "mode": "independent_review", "target_id": report["assertion_ids"][0]})
    reviewer_task = review["reviewer_tasks"][0]
    verdict = _call(
        "ponder_forge_verify",
        {
            "run_id": start["run_id"],
            "mode": "independent_review",
            "target_id": report["assertion_ids"][0],
            "reviewer_task_id": reviewer_task["task_id"],
            "reviewer_role": reviewer_task["role"],
            "independent_from_task_id": first_task["task_id"],
            "verdict": "accept",
            "confidence": 0.9,
            "rationale": "fixture fact check",
        },
    )
    assert verdict["success"] is True

    gate = _call("ponder_forge_gate_status", {"run_id": start["run_id"]})
    assert gate["success"] is True
    assert gate["status"] == "passed"

    final = _call("ponder_forge_finalize", {"run_id": start["run_id"]})
    assert final["success"] is True
    assert final["status"] == "final"
    assert "Ponder-Forge uses profile-specific evidence" in final["final_report_markdown"]
    assert "worknotes/ponder_forge_project_plan_v2.md" in final["final_report_markdown"]
    assert "不同 profile 的 evidence 类型不同" in final["final_report_markdown"]
    assert "worknotes/final.md" in final["final_report_markdown"]
    assert "fixture fact check" in final["final_report_markdown"]

    final_again = _call("ponder_forge_finalize", {"run_id": start["run_id"]})
    assert final_again["success"] is True
    assert final_again["status"] == "final"
    assert final_again["artifact_paths"]["final_md"] == final["artifact_paths"]["final_md"]

    rejected = _call(
        "ponder_forge_report_submit",
        {
            "run_id": start["run_id"],
            "task_id": first_task["task_id"],
            "role": first_task["role"],
            "summary": "late report",
            "assertions": [
                {
                    "assertion_type": "factual_claim",
                    "text": "late report must not mutate completed run",
                    "importance": 0.9,
                    "critical": True,
                    "evidence": [{"evidence_type": "source_quote", "source_ref": "late.md"}],
                }
            ],
        },
    )
    assert rejected["success"] is False
    assert "completed" in rejected["error"]
    pool_after_late = _call("ponder_forge_pool_status", {"run_id": start["run_id"]})
    assert pool_after_late["counts"]["reports"] == 1


def test_tool_handlers_return_structured_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    missing = _call("ponder_forge_plan", {})

    assert missing["success"] is False
    assert "run_id" in missing["error"]


def test_pool_status_counts_only_requested_run(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    first = _call("ponder_forge_start", {"goal": "fix pytest failure", "profile": "auto"})
    second = _call("ponder_forge_start", {"goal": "research source notes", "profile": "auto"})
    _call("ponder_forge_plan", {"run_id": first["run_id"]})
    _call("ponder_forge_plan", {"run_id": second["run_id"]})

    pool = _call("ponder_forge_pool_status", {"run_id": first["run_id"]})

    assert pool["success"] is True
    assert pool["counts"]["agent_tasks"] == 3


def test_slash_command_creates_run_and_next_instruction(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = json.loads(start_ponder_forge_command(None, "fix failing pytest in store.py"))

    assert result["success"] is True
    assert result["profile"] == "coding"
    assert result["next_tool"] == "ponder_forge_plan"
    assert result["instruction"].startswith("Call ponder_forge_plan")
