from __future__ import annotations

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
