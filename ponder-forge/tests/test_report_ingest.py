from __future__ import annotations

import planner
from graph import build_graph
from report_ingest import ingest_report
from store import PonderForgeStore


def test_ingest_report_creates_assertions_evidence_artifacts_and_edges(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = PonderForgeStore()
    store.initialize()
    run = store.create_run(goal="analyze experiment", profile="analysis")
    task = store.create_task(run["run_id"], role="metric_analyst", goal="inspect metrics")

    result = ingest_report(
        store,
        {
            "run_id": run["run_id"],
            "task_id": task["task_id"],
            "role": "metric_analyst",
            "title": "Metric analysis",
            "summary": "Accuracy improved after filtering invalid rows.",
            "confidence": 0.82,
            "assertions": [
                {
                    "assertion_type": "data_result",
                    "text": "accuracy improved by 2 points",
                    "importance": 0.9,
                    "confidence": 0.8,
                    "evidence": [
                        {
                            "evidence_type": "metric_output",
                            "source_ref": "metrics.json",
                            "quote_or_observation": '{"accuracy": 0.82}',
                            "locator": "accuracy",
                            "relevance": 0.9,
                            "reliability": 0.8,
                            "directness": 0.9,
                            "command": "python scripts/eval.py --metrics metrics.json",
                            "exit_code": 0,
                        },
                        {
                            "evidence_type": "sanity_check",
                            "source_ref": "sanity.log",
                            "quote_or_observation": "row count unchanged after transform",
                            "relevance": 0.8,
                            "reliability": 0.8,
                            "directness": 0.8,
                        },
                    ],
                }
            ],
            "artifacts": [
                {"artifact_type": "script", "path": "scripts/eval.py", "summary": "metric reproduction"}
            ],
            "open_questions": [],
        },
    )

    assert result["report_id"].startswith("pf_report_")
    assert len(result["assertion_ids"]) == 1
    assert len(result["evidence_ids"]) == 2
    assert len(result["artifact_ids"]) == 1
    assert store.count_rows("reports") == 1
    assert store.count_rows("assertions") == 1
    assert store.count_rows("evidence_items") == 2
    assert store.count_rows("artifacts") == 1
    assert store.count_rows("graph_edges") >= 4

    graph = build_graph(store, run["run_id"])
    node_types = {node["type"] for node in graph["nodes"]}
    edge_types = {edge["edge_type"] for edge in graph["edges"]}
    assert {"report", "assertion", "evidence", "artifact"} <= node_types
    assert {"produced_by", "supports", "derived_from"} <= edge_types


def test_ingest_report_normalizes_alias_payload_with_top_level_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = PonderForgeStore()
    store.initialize()
    run = store.create_run(goal="analyze experiment", profile="analysis")
    task = store.create_task(run["run_id"], role="metric_analyst", goal="inspect metrics")

    result = ingest_report(
        store,
        {
            "run_id": run["run_id"],
            "task_id": task["task_id"],
            "role": "metric_analyst",
            "summary": "Stage10 gates remain closed.",
            "assertions": [
                {
                    "type": "data_result",
                    "statement": "Stage10 downstream utility is not evaluated.",
                    "importance": 0.9,
                    "critical": True,
                    "evidence_refs": ["metric", "sanity"],
                }
            ],
            "evidence": [
                {
                    "id": "metric",
                    "type": "metric_output",
                    "source": "DOWNSTREAM_GATE_STATUS.json",
                    "summary": "downstream_gate_status=closed",
                    "command": "python scripts/read_gate.py",
                    "exit_code": 0,
                },
                {
                    "id": "sanity",
                    "type": "sanity_check",
                    "source": "STAGE10_CLAIM_LEDGER.md",
                    "summary": "downstream_utility is not_evaluated",
                },
            ],
            "artifacts": [{"kind": "report", "path": "worknotes/round4.md", "description": "round report"}],
        },
    )

    assert len(result["assertion_ids"]) == 1
    assert len(result["evidence_ids"]) == 2
    assert len(result["artifact_ids"]) == 1
    assertion = store.list_rows("assertions", run["run_id"])[0]
    assert assertion["assertion_type"] == "data_result"
    assert assertion["text"] == "Stage10 downstream utility is not evaluated."
    evidence = store.list_rows("evidence_items", run["run_id"])
    assert {row["evidence_type"] for row in evidence} == {"metric_output", "sanity_check"}
    assert any(row["command"] == "python scripts/read_gate.py" for row in evidence)
    artifact = store.list_rows("artifacts", run["run_id"])[0]
    assert artifact["artifact_type"] == "report"
    assert artifact["summary"] == "round report"


def test_ingest_report_rejects_non_array_artifacts_with_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = PonderForgeStore()
    store.initialize()
    run = store.create_run(goal="analyze experiment", profile="analysis")

    try:
        ingest_report(
            store,
            {
                "run_id": run["run_id"],
                "role": "metric_analyst",
                "summary": "agent returned artifact metadata as an object",
                "assertions": [],
                "artifacts": {"path": "lane.md", "summary": "wrong shape"},
            },
        )
    except ValueError as exc:
        assert "artifacts must be a JSON array" in str(exc)
    else:
        raise AssertionError("expected artifacts array shape error")

    assert store.count_rows("reports") == 0


def test_ingest_report_rejects_unlinked_top_level_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = PonderForgeStore()
    store.initialize()
    run = store.create_run(goal="analyze experiment", profile="analysis")

    try:
        ingest_report(
            store,
            {
                "run_id": run["run_id"],
                "role": "metric_analyst",
                "summary": "bad payload",
                "assertions": [{"assertion_type": "data_result", "text": "claim", "importance": 0.9}],
                "evidence": [{"id": "unused", "type": "metric_output", "summary": "dropped"}],
            },
        )
    except ValueError as exc:
        assert "unlinked evidence" in str(exc)
    else:
        raise AssertionError("expected unlinked evidence error")

    assert store.count_rows("reports") == 0
    assert store.count_rows("assertions") == 0
    assert store.count_rows("evidence_items") == 0


def test_ingest_report_rejects_missing_evidence_ref(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = PonderForgeStore()
    store.initialize()
    run = store.create_run(goal="analyze experiment", profile="analysis")

    try:
        ingest_report(
            store,
            {
                "run_id": run["run_id"],
                "role": "metric_analyst",
                "summary": "bad payload",
                "assertions": [
                    {
                        "assertion_type": "data_result",
                        "text": "claim",
                        "importance": 0.9,
                        "evidence_refs": ["missing"],
                    }
                ],
                "evidence": [{"id": "other", "type": "metric_output", "summary": "not linked"}],
            },
        )
    except ValueError as exc:
        assert "missing evidence_refs" in str(exc)
    else:
        raise AssertionError("expected missing evidence_refs error")

    assert store.count_rows("reports") == 0
    assert store.count_rows("assertions") == 0
    assert store.count_rows("evidence_items") == 0


def _child_report(task: dict) -> dict:
    return {
        "task_id": task["task_id"],
        "role": task["role"],
        "summary": f"completed {task['role']}",
        "assertions": [
            {
                "assertion_type": "factual_claim",
                "text": f"claim from {task['task_id']}",
                "importance": 0.9,
                "critical": True,
                "confidence": 0.8,
                "evidence": [
                    {
                        "evidence_type": "source_quote",
                        "source_ref": "source.md",
                        "quote_or_observation": "observed claim",
                    }
                ],
            }
        ],
        "artifacts": [],
    }


def _planned_lane_run(tmp_path, monkeypatch, *, top_level_runs: int = 1, child_count: int = 2):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    def _child_specs(*_args, **_kwargs):
        return [{"role": "researcher", "goal": f"child work {index}"} for index in range(1, child_count + 1)]

    monkeypatch.setattr(planner, "derive_lane_child_specs", _child_specs)
    store = PonderForgeStore()
    store.initialize()
    run = store.create_run(
        goal="research source notes",
        profile="research",
        budget={"top_level_runs": top_level_runs, "child_concurrency_per_lane": 2},
    )
    plan = planner.plan_run(store, run["run_id"])
    lanes = [task for task in plan["tasks"] if task["role"] == "swarm_lane_coordinator"]
    return store, run, plan, lanes


def test_ingest_lane_report_expands_child_reports_and_finishes_tasks(tmp_path, monkeypatch):
    store, run, plan, lanes = _planned_lane_run(tmp_path, monkeypatch)
    lane = lanes[0]
    children = [task for task in plan["tasks"] if task["parent_task_id"] == lane["task_id"]]

    result = ingest_report(
        store,
        {
            "run_id": run["run_id"],
            "task_id": lane["task_id"],
            "role": "swarm_lane_coordinator",
            "summary": "lane complete",
            "child_reports": [_child_report(child) for child in children],
            "assertions": [],
            "artifacts": [],
        },
    )

    assert len(result["child_report_ids"]) == 2
    assert store.get_task(lane["task_id"])["status"] == "finished"
    assert {store.get_task(child["task_id"])["status"] for child in children} == {"finished"}
    assert store.count_rows("reports") == 3
    assert store.count_rows("assertions") == 2


def test_ingest_lane_report_rejects_duplicate_child_report_ids(tmp_path, monkeypatch):
    store, run, plan, lanes = _planned_lane_run(tmp_path, monkeypatch)
    lane = lanes[0]
    child = next(task for task in plan["tasks"] if task["parent_task_id"] == lane["task_id"])

    try:
        ingest_report(
            store,
            {
                "run_id": run["run_id"],
                "task_id": lane["task_id"],
                "role": "swarm_lane_coordinator",
                "summary": "bad lane",
                "child_reports": [_child_report(child), _child_report(child)],
            },
        )
    except ValueError as exc:
        assert "duplicate child report task_id" in str(exc)
    else:
        raise AssertionError("expected duplicate child report task_id error")

    assert store.count_rows("reports") == 0


def test_ingest_lane_report_rejects_missing_assigned_child_report(tmp_path, monkeypatch):
    store, run, plan, lanes = _planned_lane_run(tmp_path, monkeypatch)
    lane = lanes[0]
    child = next(task for task in plan["tasks"] if task["parent_task_id"] == lane["task_id"])

    try:
        ingest_report(
            store,
            {
                "run_id": run["run_id"],
                "task_id": lane["task_id"],
                "role": "swarm_lane_coordinator",
                "summary": "bad lane",
                "child_reports": [_child_report(child)],
            },
        )
    except ValueError as exc:
        assert "missing child_reports" in str(exc)
    else:
        raise AssertionError("expected missing child_reports error")

    assert store.count_rows("reports") == 0


def test_ingest_lane_report_rejects_child_report_from_other_lane(tmp_path, monkeypatch):
    store, run, plan, lanes = _planned_lane_run(tmp_path, monkeypatch, top_level_runs=2, child_count=1)
    lane = lanes[0]
    other_lane = lanes[1]
    other_child = next(task for task in plan["tasks"] if task["parent_task_id"] == other_lane["task_id"])

    try:
        ingest_report(
            store,
            {
                "run_id": run["run_id"],
                "task_id": lane["task_id"],
                "role": "swarm_lane_coordinator",
                "summary": "bad lane",
                "child_reports": [_child_report(other_child)],
            },
        )
    except ValueError as exc:
        assert "does not belong to lane" in str(exc)
    else:
        raise AssertionError("expected does not belong to lane error")

    assert store.count_rows("reports") == 0
