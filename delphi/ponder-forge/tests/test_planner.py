import pytest
from gates import evaluate_gate
from planner import plan_run
from delegation import prepare_delegations
from report_ingest import ingest_report


def test_question_resolution_is_independent_of_worker_completion(state, run):
    rid = run["run_id"]
    question = plan_run(state, rid, {"tasks": [{"description": "Question A"}]})["task_board"][0]
    assigned = prepare_delegations(state, rid, {"tasks": [
        {"agent": "literature", "prompt": "Independent sources", "task_ids": [question["id"]]},
        {"agent": "reasoning", "prompt": "Independent derivation", "task_ids": [question["id"]]}]})
    first = assigned["assignments"][0]
    ingest_report(state, {"run_id": rid, "task_id": first["task_id"], "content": "Partial evidence"})
    assert not evaluate_gate(state, rid)["pass"]
    updated = plan_run(state, rid, {"tasks": [{"id": question["id"], "resolution": "resolved"}]})
    assert updated["task_board"][0]["owners"] == ["literature", "reasoning"]
    assert evaluate_gate(state, rid)["pass"]  # Historical unfinished assignments are not board questions.


def test_board_deduplicates_questions_and_retains_owners(state, run):
    rid = run["run_id"]
    result = plan_run(state, rid, {"tasks": [
        {"description": "A", "owners": ["one"]}, {"description": "A", "owners": ["two"]}]})
    assert len(result["task_board"]) == 1
    question = result["task_board"][0]
    assert question["owners"] == ["one", "two"]
    updated = plan_run(state, rid, {"tasks": [{"id": question["id"], "owners": ["three"], "replace_owners": True}]})
    assert updated["task_board"][0]["owners"] == ["three"]


def test_invalid_board_batch_does_not_write_partial_state(state, run):
    with pytest.raises(ValueError):
        plan_run(state, run["run_id"], {"tasks": [{"description": "A"}, {"description": "B", "resolution": "bogus"}]})
    assert state.list_rows("workflow_nodes", run["run_id"]) == []


def test_board_ids_are_scoped_to_run(state, run):
    other = state.create_run(goal="Other", profile="research")
    question = plan_run(state, other["run_id"], {"tasks": [{"description": "Other Q"}]})["task_board"][0]
    with pytest.raises(ValueError, match="belong"):
        plan_run(state, run["run_id"], {"tasks": [{"id": question["id"], "resolution": "resolved"}]})
    assert not evaluate_gate(state, other["run_id"])["pass"]


def test_rename_then_add_same_question_in_one_batch_keeps_one_identity(state, run):
    rid = run["run_id"]
    question = plan_run(state, rid, {"tasks": [{"description": "Old"}]})["task_board"][0]
    result = plan_run(state, rid, {"tasks": [
        {"id": question["id"], "description": "New", "owners": ["a"]},
        {"description": "New", "owners": ["b"]}]})
    assert len(result["task_board"]) == 1
    assert result["task_board"][0]["id"] == question["id"]
    assert result["task_board"][0]["owners"] == ["a", "b"]
