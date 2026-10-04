import json
import pytest
import cli


@pytest.fixture
def invoke(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    def call(*args):
        code = cli.main(list(args))
        output = json.loads(capsys.readouterr().out)
        assert output["success"] == (code == 0)
        return output
    return call


@pytest.mark.parametrize("level", ["high", "max"])
def test_complete_cli_workflow_and_closed_run_replay(invoke, tmp_path, level):
    started = invoke("start", "--goal", "Research a complex question", "--team-effort", level)
    rid = started["run_id"]
    assert started["team_effort"] == level
    policy = invoke("plan", "--run-id", rid)
    assert policy["coordinator_prompt"].endswith(f"<team_effort>{level}</team_effort>")
    board = tmp_path / "board.json"
    board.write_text(json.dumps({"tasks": [{"description": "A"}]}))
    question = invoke("plan", "--run-id", rid, "--file", str(board))["task_board"][0]
    assignments = tmp_path / "assign.json"
    assignments.write_text(json.dumps({"tasks": [{"agent": "a", "prompt": "Explore A", "task_ids": [question["id"]]}]}))
    tid = invoke("delegations", "--run-id", rid, "--file", str(assignments))["assignments"][0]["task_id"]
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"run_id": rid, "task_id": tid, "content": "Full result with citations"}))
    assert invoke("submit-report", "--file", str(report))["success"]
    assert not invoke("gate", "--run-id", rid)["pass"]
    draft = tmp_path / "draft.md"
    draft.write_text("# Answer\nFull result and uncertainties.")
    assert not invoke("finalize", "--run-id", rid, "--file", str(draft))["success"]
    verifier = invoke("verify", "--run-id", rid, "--file", str(draft))["assignments"][0]
    report.write_text(json.dumps({"run_id": rid, "task_id": verifier["task_id"], "content": "Independent check passed"}))
    invoke("submit-report", "--file", str(report))
    board.write_text(json.dumps({"tasks": [{"id": question["id"], "resolution": "resolved"}]}))
    invoke("plan", "--run-id", rid, "--file", str(board))
    final = invoke("finalize", "--run-id", rid, "--file", str(draft))
    assert final["status"] == "final" and final["final_report_md"] == draft.read_text()
    saved = invoke("finalize", "--run-id", rid)
    assert saved["final_report_md"] == final["final_report_md"] and saved["idempotent"]
    assert not invoke("submit-report", "--file", str(report))["success"]


def test_partial_final_retains_unresolved_questions(invoke, tmp_path):
    rid = invoke("start", "--goal", "Complex research")["run_id"]
    board = tmp_path / "board.json"
    board.write_text(json.dumps({"tasks": [{"description": "Still uncertain"}]}))
    invoke("plan", "--run-id", rid, "--file", str(board))
    draft = tmp_path / "draft.md"
    draft.write_text("What we currently know.")
    result = invoke("finalize", "--run-id", rid, "--file", str(draft), "--partial", "--reason", "Budget exhausted")
    assert result["status"] == "partial"
    assert "Still uncertain" in result["final_report_md"] and "Budget exhausted" in result["final_report_md"]
    assert not invoke("plan", "--run-id", rid, "--file", str(board))["success"]


def test_default_and_json_error_contract(invoke):
    assert invoke("start", "--goal", "Question")["team_effort"] == "max"
    assert not invoke("start", "--goal", "Question", "--team-effort", "low")["success"]
    assert not invoke("start", "--goal", "Question", "--budget", '{"delegate_batch_size":21}')["success"]
    assert not invoke("status")["success"]
