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
