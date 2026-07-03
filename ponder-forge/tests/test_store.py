from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "runs",
    "workflow_nodes",
    "agent_tasks",
    "reports",
    "assertions",
    "evidence_items",
    "graph_edges",
    "verification_verdicts",
    "final_statements",
    "statement_assertion_links",
    "events",
}


def _import_store(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sys.path.insert(0, str(ROOT))
    try:
        sys.modules.pop("store", None)
        return importlib.import_module("store")
    finally:
        sys.path.remove(str(ROOT))


def test_store_initializes_schema_under_hermes_home(tmp_path, monkeypatch):
    store_module = _import_store(monkeypatch, tmp_path)
    store = store_module.PonderForgeStore()

    store.initialize()

    assert store.db_path == tmp_path / "ponder_forge" / "state.sqlite3"
    assert store.db_path.exists()
    with sqlite3.connect(store.db_path) as conn:
        tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
    assert EXPECTED_TABLES <= tables


def test_store_creates_run_task_report_and_jsonl_event(tmp_path, monkeypatch):
    store_module = _import_store(monkeypatch, tmp_path)
    store = store_module.PonderForgeStore()
    store.initialize()

    run = store.create_run(goal="fix complex bug", profile="coding", budget={"max_waves": 1})
    task = store.create_task(run["run_id"], role="developer", goal="find root cause")
    event = store.append_event(run["run_id"], "test_event", {"task_id": task["task_id"]}, task_id=task["task_id"])

    fetched = store.get_run(run["run_id"])
    assert fetched["user_goal"] == "fix complex bug"
    assert fetched["profile"] == "coding"
    assert json.loads(fetched["budget_json"]) == {"max_waves": 1}
    assert task["run_id"] == run["run_id"]
    assert event["event_type"] == "test_event"

    events_path = tmp_path / "ponder_forge" / "runs" / run["run_id"] / "events.jsonl"
    assert events_path.exists()
    lines = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    assert [line["event_type"] for line in lines] == ["run_created", "task_created", "test_event"]


def test_store_records_report_assertion_evidence_and_edges(tmp_path, monkeypatch):
    store_module = _import_store(monkeypatch, tmp_path)
    store = store_module.PonderForgeStore()
    store.initialize()
    run = store.create_run(goal="analyze metric", profile="analysis")
    task = store.create_task(run["run_id"], role="metric_analyst", goal="inspect metric")

    report = store.create_report(
        run_id=run["run_id"],
        task_id=task["task_id"],
        role="metric_analyst",
        title="metric result",
        summary="accuracy improved",
        confidence=0.8,
        raw={"source": "test"},
    )
    assertion = store.create_assertion(
        run_id=run["run_id"],
        report_id=report["report_id"],
        profile="analysis",
        assertion_type="data_result",
        text="accuracy improved by 2 points",
        importance=0.9,
        confidence=0.7,
        raw={"critical": True},
    )
    evidence = store.create_evidence(
        run_id=run["run_id"],
        report_id=report["report_id"],
        assertion_id=assertion["assertion_id"],
        evidence_type="metric_output",
        source_ref="metrics.json",
        quote_or_observation='{"accuracy": 0.82}',
        relevance=0.9,
        reliability=0.8,
        directness=0.9,
        raw={"metric": "accuracy"},
    )
    edge = store.create_edge(
        run_id=run["run_id"],
        src_type="evidence",
        src_id=evidence["evidence_id"],
        dst_type="assertion",
        dst_id=assertion["assertion_id"],
        edge_type="supports",
    )

    assert report["report_id"].startswith("pf_report_")
    assert assertion["assertion_id"].startswith("pf_assertion_")
    assert evidence["directness"] == 0.9
    assert edge["edge_type"] == "supports"
    assert store.count_rows("reports") == 1
    assert store.count_rows("assertions") == 1
    assert store.count_rows("evidence_items") == 1
    assert store.count_rows("graph_edges") == 1
