import pytest
from delegation import prepare_delegations, record_dispatch
from planner import plan_run
from report_ingest import ingest_report


def test_scoped_assignments_can_continue_an_agent_with_full_report(state, run):
    rid = run["run_id"]
    initial = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "Research A"}]})
    task = initial["assignments"][0]
    record_dispatch(state, rid, task["task_id"], host_agent_id="host-a")
    full_text = "Finding with precise values 123.456 and caveats\n" + "Detail " * 300
    ingest_report(state, {"run_id": rid, "task_id": task["task_id"], "content": full_text})
    follow_up = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": 'Check again <attach agent="a"/>'}]})
    assert full_text in follow_up["assignments"][0]["prompt"]
    assert follow_up["assignments"][0]["task_id"] != task["task_id"]
    assert state.get_task(task["task_id"])["status"] == "finished"


def test_attachment_cannot_leak_another_run_report(state, run):
    other = state.create_run(goal="Other", profile="research")
    task = prepare_delegations(state, other["run_id"], {"tasks": [{"agent": "private", "prompt": "Secret"}]})["assignments"][0]
    ingest_report(state, {"run_id": other["run_id"], "task_id": task["task_id"], "content": "other run"})
    with pytest.raises(ValueError, match="attachment"):
        prepare_delegations(state, run["run_id"], {"tasks": [{"agent": "reader", "prompt": '<attach agent="private"/>'}]})
    assert state.list_rows("agent_tasks", run["run_id"]) == []


def test_prepare_does_not_claim_launch_and_receipt_records_actual_host(state, run):
    rid = run["run_id"]
    prepared = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "Work"}]})
    tid = prepared["assignments"][0]["task_id"]
    assert state.get_task(tid)["status"] == "queued"
    assert len(prepare_delegations(state, rid)["assignments"]) == 1
    record_dispatch(state, rid, tid, host_agent_id="native-17")
    assert prepare_delegations(state, rid)["assignments"] == []
    assert state.get_task(tid)["hermes_subagent_id"] == "native-17"
    with pytest.raises(ValueError, match="different"):
        record_dispatch(state, rid, tid, host_agent_id="native-18")
    record_dispatch(state, rid, tid, cancelled=True)
    assert state.get_task(tid)["status"] == "cancelled"


def test_assignment_batch_is_validated_before_writes(state, run):
    with pytest.raises(ValueError):
        prepare_delegations(state, run["run_id"], {"tasks": [
            {"agent": "a", "prompt": "valid"}, {"agent": "b", "prompt": "bad", "task_ids": ["foreign"]}]})
    assert state.list_rows("agent_tasks", run["run_id"]) == []
