import pytest
import sqlite3
from delegation import prepare_delegations, report_content
from report_ingest import ingest_report


def test_full_report_survives_and_duplicate_submission_is_idempotent(state, run):
    rid = run["run_id"]
    tid = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "Work"}]})["assignments"][0]["task_id"]
    content = "Exact report\nURL https://example.com\n" + "caveat " * 2000
    payload = {"run_id": rid, "task_id": tid, "content": content}
    first = ingest_report(state, payload)
    second = ingest_report(state, payload)
    assert first["report_id"] == second["report_id"]
    assert report_content(state.get_report(first["report_id"])) == content
    assert len(state.list_rows("reports", rid)) == 1
    state.update_task_status(tid, "running")
    repaired = ingest_report(state, payload)
    assert repaired["idempotent"] is True
    assert state.get_task(tid)["status"] == "finished"


@pytest.mark.parametrize("status", ["partial", "failed", "cancelled"])
def test_negative_and_interrupted_results_are_retained(state, run, status):
    rid = run["run_id"]
    task = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "Work"}]})["assignments"][0]
    report = ingest_report(state, {"run_id": rid, "task_id": task["task_id"], "content": "No supporting result", "status": status})
    assert report_content(state.get_report(report["report_id"])) == "No supporting result"
    assert state.get_task(task["task_id"])["status"] == status


def test_cross_run_report_is_rejected_without_writing(state, run):
    other = state.create_run(goal="Other", profile="research")
    task = prepare_delegations(state, other["run_id"], {"tasks": [{"agent": "a", "prompt": "Work"}]})["assignments"][0]
    with pytest.raises(ValueError, match="belong"):
        ingest_report(state, {"run_id": run["run_id"], "task_id": task["task_id"], "content": "wrong run"})
    assert state.list_rows("reports") == []
    assert state.get_task(task["task_id"])["status"] == "queued"


@pytest.mark.parametrize("bad", [{"content": ""}, {"confidence": 2}, {"title": []}])
def test_invalid_report_does_not_finish_task(state, run, bad):
    rid = run["run_id"]
    task = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "Work"}]})["assignments"][0]
    with pytest.raises(ValueError):
        ingest_report(state, {"run_id": rid, "task_id": task["task_id"], "content": "Report", **bad})
    assert state.get_task(task["task_id"])["status"] == "queued"
    assert state.list_rows("reports") == []


def test_report_and_event_roll_back_when_task_update_fails(state, run):
    rid = run["run_id"]
    tid = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "Work"}]})["assignments"][0]["task_id"]
    payload = {"run_id": rid, "task_id": tid, "report_id": "delivery-a", "content": "Complete result"}
    with state.connect() as conn:
        conn.execute("CREATE TRIGGER fail_status BEFORE UPDATE ON agent_tasks BEGIN SELECT RAISE(ABORT, 'status failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="status failure"):
        ingest_report(state, payload)
    assert state.list_rows("reports", rid) == []
    assert not [event for event in state.list_rows("events", rid) if event["event_type"] == "report_created"]
    assert state.get_task(tid)["status"] == "queued"
    with state.connect() as conn:
        conn.execute("DROP TRIGGER fail_status")
    first = ingest_report(state, payload)
    assert state.get_task(tid)["status"] == "finished"
    assert ingest_report(state, payload)["report_id"] == first["report_id"]
    assert len(state.list_rows("reports", rid)) == 1


def test_old_report_retry_does_not_regress_terminal_status(state, run, monkeypatch):
    rid = run["run_id"]
    tid = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "Work"}]})["assignments"][0]["task_id"]
    partial = {"run_id": rid, "task_id": tid, "content": "Partial", "status": "partial"}
    ingest_report(state, partial)
    def fail_projection(*args):
        raise OSError("disk full")
    monkeypatch.setattr(state, "_append_jsonl", fail_projection)
    finished = ingest_report(state, {"run_id": rid, "task_id": tid, "content": "Complete"})
    assert finished["event_log_warning"] == "disk full"
    assert ingest_report(state, partial)["status"] == "finished"
    assert state.get_task(tid)["status"] == "finished"
