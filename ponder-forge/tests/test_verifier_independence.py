from __future__ import annotations

import importlib.util
from argparse import Namespace
from pathlib import Path

import pytest

from gates import evaluate_gate
from planner import plan_run
from report_ingest import ingest_report
from store import PonderForgeStore
from verifier import verify_run

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    spec = importlib.util.spec_from_file_location("ponder_forge_cli_verifier_test", ROOT / "cli.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLI = _load_cli()


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def _supported_coding_run() -> tuple[PonderForgeStore, str, str, str]:
    start = CLI.start_run("fix failing pytest", profile="coding")
    store = _store()
    plan = plan_run(store, start["run_id"])
    producer_task = plan["tasks"][0]
    report = ingest_report(
        store,
        {
            "run_id": start["run_id"],
            "task_id": producer_task["task_id"],
            "role": producer_task["role"],
            "summary": "fixed root cause with tests",
            "assertions": [
                {
                    "assertion_type": "code_change_claim",
                    "text": "The failing pytest is fixed by a causal code change",
                    "importance": 0.95,
                    "critical": True,
                    "evidence": [
                        {
                            "evidence_type": "passing_test",
                            "source_ref": "pytest",
                            "quote_or_observation": "1 passed",
                            "exit_code": 0,
                            "directness": 0.9,
                        },
                        {
                            "evidence_type": "root_cause_trace",
                            "source_ref": "store.py",
                            "quote_or_observation": "causal patch",
                            "directness": 0.9,
                        },
                    ],
                }
            ],
        },
    )
    return store, start["run_id"], report["assertion_ids"][0], producer_task["task_id"]


def test_precheck_cannot_satisfy_critical_verdict_or_finalize(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, run_id, assertion_id, _producer_task_id = _supported_coding_run()

    precheck = verify_run(store, run_id, {"run_id": run_id, "mode": "precheck", "target_id": assertion_id})
    gate = evaluate_gate(store, run_id)
    final = CLI.cmd_finalize(Namespace(run_id=run_id))

    assert precheck["verifier_mode"] == "precheck"
    assert precheck["final_verdict"] is False
    assert gate["status"] == "blocked"
    assert any(gap.get("gap_type") == "missing_independent_verdict" for gap in gate["gaps"])
    assert final["status"] == "blocked"


def test_independent_review_task_and_verdict_allow_finalize(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, run_id, assertion_id, producer_task_id = _supported_coding_run()

    review = verify_run(store, run_id, {"run_id": run_id, "mode": "independent_review", "target_id": assertion_id})
    assert review["reviewer_tasks"]
    reviewer_task = review["reviewer_tasks"][0]
    assert reviewer_task["role"] == "causality_reviewer"
    assert producer_task_id != reviewer_task["task_id"]
    assert producer_task_id in reviewer_task["context"]

    verdict = verify_run(
        store,
        run_id,
        {
            "run_id": run_id,
            "mode": "independent_review",
            "target_id": assertion_id,
            "reviewer_task_id": reviewer_task["task_id"],
            "reviewer_role": reviewer_task["role"],
            "independent_from_task_id": producer_task_id,
            "verdict": "accept",
            "confidence": 0.88,
            "rationale": "reviewed diff and test evidence independently",
        },
    )
    gate = evaluate_gate(store, run_id)
    final = CLI.cmd_finalize(Namespace(run_id=run_id))

    assert verdict["recorded_verdict"]["verifier_mode"] == "independent_review"
    assert verdict["recorded_verdict"]["independent_from_task_id"] == producer_task_id
    assert gate["status"] == "passed"
    assert final["status"] == "final"


def test_non_independent_verdict_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, run_id, assertion_id, producer_task_id = _supported_coding_run()

    with pytest.raises(ValueError, match="not independent"):
        verify_run(
            store,
            run_id,
            {
                "run_id": run_id,
                "mode": "independent_review",
                "target_id": assertion_id,
                "reviewer_task_id": producer_task_id,
                "reviewer_role": "developer",
                "independent_from_task_id": producer_task_id,
                "verdict": "accept",
            },
        )


def test_independent_review_task_creation_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store, run_id, assertion_id, _producer_task_id = _supported_coding_run()

    first = verify_run(store, run_id, {"run_id": run_id, "mode": "independent_review", "target_id": assertion_id})
    second = verify_run(store, run_id, {"run_id": run_id, "mode": "independent_review", "target_id": assertion_id})

    assert first["reviewer_tasks"][0]["task_id"] == second["reviewer_tasks"][0]["task_id"]
