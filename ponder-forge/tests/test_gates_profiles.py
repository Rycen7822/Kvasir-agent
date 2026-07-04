from __future__ import annotations

import planner
from gates import evaluate_gate
from renderer import render_final_report
from report_ingest import ingest_report
from store import PonderForgeStore


def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = PonderForgeStore()
    store.initialize()
    return store


def _run_with_report(store, profile: str, assertion_type: str, evidence: list[dict]):
    run = store.create_run(goal=f"{profile} task", profile=profile)
    task = store.create_task(run["run_id"], role="tester", goal="produce report")
    result = ingest_report(
        store,
        {
            "run_id": run["run_id"],
            "task_id": task["task_id"],
            "role": "tester",
            "summary": "critical assertion",
            "assertions": [
                {
                    "assertion_type": assertion_type,
                    "text": f"critical {profile} assertion",
                    "importance": 0.95,
                    "confidence": 0.8,
                    "evidence": evidence,
                    "critical": True,
                }
            ],
        },
    )
    return run["run_id"], result["assertion_ids"][0]


def _accept_with_independent_verdict(store, run_id: str, assertion_id: str):
    assertion = [row for row in store.list_rows("assertions", run_id) if row["assertion_id"] == assertion_id][0]
    report = store.get_report(assertion["report_id"])
    producer_task_id = report["task_id"]
    run = store.get_run(run_id)
    reviewer = store.create_task(run_id, role="independent_reviewer", goal="review assertion", parent_task_id=producer_task_id)
    store.create_verdict(
        run_id=run_id,
        profile=run["profile"],
        target_type="assertion",
        target_id=assertion_id,
        reviewer_role="independent_reviewer",
        reviewer_task_id=reviewer["task_id"],
        verifier_mode="independent_review",
        independent_from_task_id=producer_task_id,
        verdict="accept",
        confidence=0.9,
        rationale="fixture independent review",
    )
    store.update_assertion_status(assertion_id, "accepted")


def _swarm_child_report(task: dict) -> dict:
    return {
        "task_id": task["task_id"],
        "role": task["role"],
        "summary": f"finished {task['role']}",
        "assertions": [
            {
                "assertion_type": "factual_claim",
                "text": f"supported child claim {task['task_id']}",
                "importance": 0.95,
                "critical": True,
                "confidence": 0.8,
                "evidence": [
                    {
                        "evidence_type": "source_quote",
                        "source_ref": "source.md",
                        "quote_or_observation": "quoted fact",
                    }
                ],
            }
        ],
        "artifacts": [],
    }


def _two_lane_swarm(store, monkeypatch):
    def _one_child(*_args, **_kwargs):
        return [{"role": "researcher", "goal": "child work"}]

    monkeypatch.setattr(planner, "derive_lane_child_specs", _one_child)
    run = store.create_run(
        goal="research source notes",
        profile="research",
        budget={"top_level_runs": 2, "child_concurrency_per_lane": 1},
    )
    plan = planner.plan_run(store, run["run_id"])
    lanes = [task for task in plan["tasks"] if task["role"] == "swarm_lane_coordinator"]
    return run, lanes, plan["tasks"]


def _submit_lane_report(store, run_id: str, lane: dict, tasks: list[dict]) -> list[str]:
    children = [task for task in tasks if task["parent_task_id"] == lane["task_id"]]
    result = ingest_report(
        store,
        {
            "run_id": run_id,
            "task_id": lane["task_id"],
            "role": "swarm_lane_coordinator",
            "summary": "lane complete",
            "child_reports": [_swarm_child_report(child) for child in children],
            "assertions": [],
            "artifacts": [],
        },
    )
    child_report_ids = set(result["child_report_ids"])
    return [
        assertion["assertion_id"]
        for assertion in store.list_rows("assertions", run_id)
        if assertion["report_id"] in child_report_ids
    ]


def test_swarm_gate_blocks_until_all_lane_and_child_tasks_finish(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run, lanes, tasks = _two_lane_swarm(store, monkeypatch)
    assertion_ids = _submit_lane_report(store, run["run_id"], lanes[0], tasks)
    for assertion_id in assertion_ids:
        _accept_with_independent_verdict(store, run["run_id"], assertion_id)

    gate = evaluate_gate(store, run["run_id"])

    assert gate["status"] == "blocked"
    assert any(gap.get("gap_type") == "incomplete_swarm_topology" for gap in gate["gaps"])
    assert gate["finalize_allowed"] is False


def test_swarm_gate_passes_after_all_lane_and_child_tasks_finish(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run, lanes, tasks = _two_lane_swarm(store, monkeypatch)
    assertion_ids: list[str] = []
    for lane in lanes:
        assertion_ids.extend(_submit_lane_report(store, run["run_id"], lane, tasks))
    for assertion_id in assertion_ids:
        _accept_with_independent_verdict(store, run["run_id"], assertion_id)

    gate = evaluate_gate(store, run["run_id"])

    assert gate["status"] == "passed"
    assert gate["finalize_allowed"] is True


def test_profile_gates_block_missing_required_evidence(tmp_path, monkeypatch):
    cases = [
        ("research", "factual_claim", []),
        ("coding", "code_claim", [{"evidence_type": "code_pointer", "source_ref": "app.py:10"}]),
        ("design", "design_decision", [{"evidence_type": "requirement", "source_ref": "request"}]),
        ("analysis", "data_result", [{"evidence_type": "metric_output", "source_ref": "metrics.json"}]),
        ("math", "proof_step", [{"evidence_type": "proof_step", "source_ref": "attempt"}]),
    ]
    for profile, assertion_type, evidence in cases:
        store = _store(tmp_path / profile, monkeypatch)
        run_id, assertion_id = _run_with_report(store, profile, assertion_type, evidence)
        _accept_with_independent_verdict(store, run_id, assertion_id)

        gate = evaluate_gate(store, run_id)

        assert gate["status"] == "blocked", profile
        assert gate["finalize_allowed"] is False
        assert gate["metrics"]["unsupported_critical_assertions"] == 1
        assert gate["gaps"]


def test_analysis_gate_explains_missing_metric_command(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run_id, assertion_id = _run_with_report(
        store,
        "analysis",
        "data_result",
        [
            {"evidence_type": "metric_output", "source_ref": "metrics.json"},
            {"evidence_type": "transform_script", "source_ref": "eval.py"},
            {"evidence_type": "sanity_check", "source_ref": "sanity.log"},
        ],
    )
    _accept_with_independent_verdict(store, run_id, assertion_id)

    gate = evaluate_gate(store, run_id)

    assert gate["status"] == "blocked"
    assert any("metric_output.command" in gap.get("profile_specific_reason", "") for gap in gate["gaps"])


def test_analysis_gate_blocks_nonzero_metric_exit_code(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run_id, assertion_id = _run_with_report(
        store,
        "analysis",
        "data_result",
        [
            {"evidence_type": "metric_output", "source_ref": "metrics.json", "command": "python eval.py", "exit_code": 1},
            {"evidence_type": "transform_script", "source_ref": "eval.py"},
            {"evidence_type": "sanity_check", "source_ref": "sanity.log"},
        ],
    )
    _accept_with_independent_verdict(store, run_id, assertion_id)

    gate = evaluate_gate(store, run_id)

    assert gate["status"] == "blocked"
    assert any("exit_code" in gap.get("profile_specific_reason", "") for gap in gate["gaps"])
    assert any(gap.get("gap_type") == "missing_profile_evidence" for gap in gate["gaps"])


def test_gate_metrics_report_real_coverage_for_passed_artifact_backed_assertion(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run = store.create_run(goal="research task", profile="research")
    task = store.create_task(run["run_id"], role="researcher", goal="produce report")
    result = ingest_report(
        store,
        {
            "run_id": run["run_id"],
            "task_id": task["task_id"],
            "role": "researcher",
            "summary": "supported fact",
            "assertions": [
                {
                    "assertion_type": "factual_claim",
                    "text": "artifact-backed supported fact",
                    "importance": 0.95,
                    "critical": True,
                    "evidence": [
                        {"evidence_type": "source_quote", "source_ref": "note.md", "quote_or_observation": "quoted"},
                        {"evidence_type": "definition_boundary", "source_ref": "boundary.md"},
                    ],
                }
            ],
            "artifacts": [{"artifact_type": "analysis_report", "path": "report.md", "summary": "fixture"}],
        },
    )
    _accept_with_independent_verdict(store, run["run_id"], result["assertion_ids"][0])

    gate = evaluate_gate(store, run["run_id"])

    assert gate["status"] == "passed"
    assert gate["metrics"]["independent_review_coverage"] == 1.0
    assert gate["metrics"]["artifact_reproducibility_coverage"] == 1.0
    assert gate["metrics"]["final_statement_trace_coverage"] == 1.0
    assert gate["metrics"]["blocking_gap_count"] == 0


def test_coding_gate_blocks_failing_test_without_successful_execution(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run_id, assertion_id = _run_with_report(
        store,
        "coding",
        "code_claim",
        [
            {"evidence_type": "root_cause_trace", "source_ref": "bug.md"},
            {"evidence_type": "failing_test", "source_ref": "pytest.log", "command": "pytest", "exit_code": 1},
        ],
    )
    _accept_with_independent_verdict(store, run_id, assertion_id)

    gate = evaluate_gate(store, run_id)

    assert gate["status"] == "blocked"
    assert any("successful" in gap.get("profile_specific_reason", "") for gap in gate["gaps"])


def test_gate_metrics_distinguish_unsupported_assertions_from_gap_count(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run_id, _assertion_id = _run_with_report(store, "research", "factual_claim", [])

    gate = evaluate_gate(store, run_id)

    assert gate["status"] == "blocked"
    assert gate["metrics"]["unsupported_critical_assertions"] == 1
    assert gate["metrics"]["blocking_gap_count"] == 2
    assert gate["metrics"]["independent_review_coverage"] == 0.0
    assert gate["metrics"]["final_statement_trace_coverage"] == 0.0


def test_math_counterexample_gap_distinguishes_resolved_search_from_positive_counterexample(tmp_path, monkeypatch):
    store = _store(tmp_path / "resolved", monkeypatch)
    run_id, assertion_id = _run_with_report(
        store,
        "math",
        "proof_step",
        [
            {"evidence_type": "proof_step", "source_ref": "proof.md"},
            {"evidence_type": "critique", "source_ref": "review.md"},
            {"evidence_type": "counterexample", "source_ref": "search.md", "quote_or_observation": "counterexample search found none", "resolved": True},
        ],
    )
    _accept_with_independent_verdict(store, run_id, assertion_id)

    resolved_gate = evaluate_gate(store, run_id)

    assert resolved_gate["status"] == "passed"

    store = _store(tmp_path / "positive", monkeypatch)
    run_id, assertion_id = _run_with_report(
        store,
        "math",
        "proof_step",
        [
            {"evidence_type": "proof_step", "source_ref": "proof.md"},
            {"evidence_type": "critique", "source_ref": "review.md"},
            {"evidence_type": "counterexample", "source_ref": "search.md", "quote_or_observation": "positive counterexample found"},
        ],
    )
    _accept_with_independent_verdict(store, run_id, assertion_id)

    positive_gate = evaluate_gate(store, run_id)

    assert positive_gate["status"] == "blocked"
    assert any("counterexample" in gap.get("profile_specific_reason", "") for gap in positive_gate["gaps"])


def test_profile_gates_pass_supported_profile_evidence(tmp_path, monkeypatch):
    cases = [
        (
            "research",
            "factual_claim",
            [
                {"evidence_type": "source_quote", "source_ref": "note.md", "quote_or_observation": "quoted fact", "directness": 0.9},
                {"evidence_type": "definition_boundary", "source_ref": "note.md"},
            ],
        ),
        (
            "coding",
            "code_claim",
            [
                {"evidence_type": "root_cause_trace", "source_ref": "bug.md"},
                {"evidence_type": "execution_log", "source_ref": "pytest.log", "command": "pytest", "exit_code": 0},
                {"evidence_type": "passing_test", "source_ref": "tests/test_bug.py"},
            ],
        ),
        (
            "design",
            "design_decision",
            [
                {"evidence_type": "constraint", "source_ref": "plan"},
                {"evidence_type": "existing_owner_seam", "source_ref": "module.py"},
                {"evidence_type": "decision_reason", "source_ref": "adr"},
            ],
        ),
        (
            "analysis",
            "data_result",
            [
                {"evidence_type": "metric_output", "source_ref": "metrics.json", "command": "python eval.py", "exit_code": 0},
                {"evidence_type": "transform_script", "source_ref": "eval.py"},
                {"evidence_type": "sanity_check", "source_ref": "sanity.log"},
            ],
        ),
        (
            "math",
            "proof_step",
            [
                {"evidence_type": "proof_step", "source_ref": "attempt"},
                {"evidence_type": "critique", "source_ref": "review"},
                {"evidence_type": "revision_trace", "source_ref": "attempt2"},
            ],
        ),
    ]
    for profile, assertion_type, evidence in cases:
        store = _store(tmp_path / profile, monkeypatch)
        run_id, assertion_id = _run_with_report(store, profile, assertion_type, evidence)
        _accept_with_independent_verdict(store, run_id, assertion_id)

        gate = evaluate_gate(store, run_id)

        assert gate["status"] == "passed", profile
        assert gate["finalize_allowed"] is True
        assert gate["metrics"]["unsupported_critical_assertions"] == 0


def test_renderer_blocks_unlinked_final_statement_and_renders_linked_accepted_assertion(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run_id, assertion_id = _run_with_report(
        store,
        "research",
        "factual_claim",
        [{"evidence_type": "source_quote", "source_ref": "note.md", "quote_or_observation": "quoted fact"}],
    )
    statement = store.create_final_statement(run_id, section="Findings", text="critical research assertion")

    blocked = render_final_report(store, run_id)
    assert blocked["status"] == "blocked"
    assert blocked["gaps"][0]["reason"] == "final statement has no accepted assertion link"

    store.update_assertion_status(assertion_id, "accepted")
    assertion = [row for row in store.list_rows("assertions", run_id) if row["assertion_id"] == assertion_id][0]
    report = store.get_report(assertion["report_id"])
    assert report is not None
    reviewer = store.create_task(run_id, role="independent_reviewer", goal="review assertion", parent_task_id=report["task_id"])
    store.create_verdict(
        run_id=run_id,
        profile="research",
        target_type="assertion",
        target_id=assertion_id,
        reviewer_role="independent_reviewer",
        reviewer_task_id=reviewer["task_id"],
        verifier_mode="independent_review",
        independent_from_task_id=report["task_id"],
        verdict="accept",
        confidence=0.9,
        rationale="fixture independent review",
    )
    store.create_artifact(
        run_id=run_id,
        report_id=assertion["report_id"],
        artifact_type="analysis_report",
        path="artifact.md",
        summary="fixture artifact summary",
    )
    store.link_final_statement(statement["statement_id"], assertion_id, relation="rendered_as")
    final = render_final_report(store, run_id)

    assert final["status"] == "final"
    assert "critical research assertion" in final["final_report_markdown"]
    assert "note.md" in final["final_report_markdown"]
    assert "quoted fact" in final["final_report_markdown"]
    assert "artifact.md" in final["final_report_markdown"]
    assert "fixture independent review" in final["final_report_markdown"]
    assert final["artifact_paths"]["final_md"].endswith("final.md")


def test_renderer_auto_statements_are_linked_to_accepted_assertions(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    run_id, assertion_id = _run_with_report(
        store,
        "research",
        "factual_claim",
        [{"evidence_type": "source_quote", "source_ref": "note.md", "quote_or_observation": "quoted fact"}],
    )
    store.update_assertion_status(assertion_id, "accepted")

    final = render_final_report(store, run_id)
    statement = store.list_rows("final_statements", run_id)[0]

    assert final["status"] == "final"
    assert store.list_rows("statement_assertion_links") == [
        {
            "statement_id": statement["statement_id"],
            "assertion_id": assertion_id,
            "relation": "rendered_as",
        }
    ]
