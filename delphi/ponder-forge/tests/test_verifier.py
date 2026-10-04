import pytest
from delegation import prepare_delegations
from report_ingest import ingest_report
from verifier import verify_run


def test_final_verifier_receives_original_question_and_unabridged_draft(state, run):
    draft = "Proposed answer\n" + "precise atoms 12.345 caveats " * 600
    result = verify_run(state, run["run_id"], {"mode": "final", "draft": draft})
    task = result["assignments"][0]
    assert run["user_goal"] in task["prompt"]
    assert draft in task["prompt"]
    assert task["agent"] == "final_verifier"
    assert "Completeness Check" in task["system_prompt"]
    assert "return as your final reply" in task["system_prompt"]


def test_local_arbitration_receives_both_full_reports(state, run):
    rid = run["run_id"]
    tasks = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "A"}, {"agent": "b", "prompt": "B"}]})["assignments"]
    reports = []
    for task in tasks:
        reports.append(ingest_report(state, {"run_id": rid, "task_id": task["task_id"], "content": task["agent"] * 2000}))
    result = verify_run(state, rid, {"mode": "local", "conflict": "Which number is correct?", "report_ids": [x["report_id"] for x in reports]})
    task = result["assignments"][0]
    assert task["agent"] == "local_verifier"
    assert "a" * 2000 in task["prompt"] and "b" * 2000 in task["prompt"]
    assert "Which number is correct?" in task["prompt"]


def test_invalid_local_reference_does_not_create_verifier(state, run):
    with pytest.raises(ValueError):
        verify_run(state, run["run_id"], {"mode": "local", "conflict": "A/B", "report_ids": ["not-a", "not-b"]})
    assert state.list_rows("agent_tasks") == []
