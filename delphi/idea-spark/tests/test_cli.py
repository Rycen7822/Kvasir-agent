import io
import json
from pathlib import Path

import pytest

from idea_spark import cli
from idea_spark.config import config_path


def _read_stdout_json(capsys):
    captured = capsys.readouterr()
    return json.loads(captured.out)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_cli_config_show_and_set_tools(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert cli.main(["config", "show"]) == 0
    shown = _read_stdout_json(capsys)
    assert shown == {
        "success": True,
        "path": str(config_path()),
        "config": {"tools": {"enabled": False}},
    }

    assert cli.main(["config", "set-tools", "true"]) == 0
    enabled = _read_stdout_json(capsys)
    assert enabled["success"] is True
    assert enabled["tools_enabled"] is True
    assert json.loads(config_path().read_text(encoding="utf-8")) == {"tools": {"enabled": True}}

    assert cli.main(["config", "set-tools", "false"]) == 0
    disabled = _read_stdout_json(capsys)
    assert disabled["tools_enabled"] is False


def test_cli_rejects_invalid_json_payload_file(tmp_path, capsys):
    payload = tmp_path / "bad.json"
    payload.write_text("not-json", encoding="utf-8")

    assert cli.main(["call", "idea_spark_room_create", "--json-file", str(payload)]) == 1
    result = _read_stdout_json(capsys)
    assert result["success"] is False
    assert result["operation"] == "idea_spark_room_create"
    assert "invalid JSON payload" in result["error"]


def test_cli_rejects_non_object_stdin_payload(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("[]"))

    assert cli.main(["call", "idea_spark_room_create", "--stdin"]) == 1
    result = _read_stdout_json(capsys)
    assert result["success"] is False
    assert result["operation"] == "idea_spark_room_create"
    assert result["error"] == "payload must be a JSON object"


def test_cli_rejects_unknown_operation(capsys):
    assert cli.main(["call", "idea_spark_nope"]) == 1
    result = _read_stdout_json(capsys)
    assert result == {"success": False, "error": "unknown operation", "operation": "idea_spark_nope"}


def test_hermes_cli_wrapper_propagates_failure_exit_code(capsys):
    args = cli.build_parser().parse_args(["call", "idea_spark_nope"])

    with pytest.raises(SystemExit) as exc:
        cli.hermes_main_from_args(args)

    assert exc.value.code == 1
    result = _read_stdout_json(capsys)
    assert result == {"success": False, "error": "unknown operation", "operation": "idea_spark_nope"}


def test_cli_call_room_lifecycle_with_json_files(temp_idea_spark_db, tmp_path, capsys):
    room_id = "cli-lifecycle"

    assert (
        cli.main(
            [
                "call",
                "idea_spark_room_create",
                "--json-file",
                str(_write_json(tmp_path / "room.json", {"room_id": room_id, "title": "CLI lifecycle", "topic": "config-gated default CLI mode", "created_by": "test"})),
            ]
        )
        == 0
    )
    room = _read_stdout_json(capsys)
    assert room["success"] is True
    assert room["room_id"] == room_id
    assert room["room_url"] == f"http://127.0.0.1:8765/room/{room_id}"

    assert (
        cli.main(
            [
                "call",
                "idea_spark_room_join",
                "--json-file",
                str(_write_json(tmp_path / "join.json", {"room_id": room_id, "agent_id": "reader", "role": "Reviewer"})),
            ]
        )
        == 0
    )
    assert _read_stdout_json(capsys)["success"] is True

    artifact_payload = {
        "room_id": room_id,
        "type": "AtomicClaim",
        "title": "CLI preserves markdown payloads",
        "content": "Line 1\n\n| Metric | Value |\n|---|---|\n| CLI | works |",
        "created_by": "reader",
    }
    assert (
        cli.main(
            [
                "call",
                "idea_spark_artifact_create",
                "--json-file",
                str(_write_json(tmp_path / "artifact.json", artifact_payload)),
            ]
        )
        == 0
    )
    artifact = _read_stdout_json(capsys)
    assert artifact["success"] is True
    artifact_id = artifact["artifact_id"]

    assert (
        cli.main(
            [
                "call",
                "idea_spark_message_post",
                "--json-file",
                str(
                    _write_json(
                        tmp_path / "message.json",
                        {
                            "room_id": room_id,
                            "agent_id": "reader",
                            "round_id": "r1",
                            "phase": "review",
                            "content": "CLI lifecycle message",
                            "artifact_ids": [artifact_id],
                        },
                    )
                ),
            ]
        )
        == 0
    )
    assert _read_stdout_json(capsys)["success"] is True

    gate_payload = {
        "room_id": room_id,
        "gate_type": "implementation-smoke",
        "decision": "accepted",
        "input_artifact_ids": [artifact_id],
        "rationale": "CLI can record gate-backed final conclusions.",
        "decided_by": "gatekeeper",
        "close_room": True,
    }
    assert (
        cli.main(
            [
                "call",
                "idea_spark_gate_record",
                "--json-file",
                str(_write_json(tmp_path / "gate.json", gate_payload)),
            ]
        )
        == 0
    )
    gate = _read_stdout_json(capsys)
    assert gate["success"] is True
    assert gate["room_status"] == "gated"

    assert (
        cli.main(
            [
                "call",
                "idea_spark_room_export",
                "--json-file",
                str(_write_json(tmp_path / "export.json", {"room_id": room_id})),
            ]
        )
        == 0
    )
    exported = _read_stdout_json(capsys)
    assert exported["success"] is True
    assert exported["artifact_count"] >= 2
    assert exported["gate_count"] == 1
    assert "# Idea-Spark Room Report" in exported["markdown"]
    assert "CLI preserves markdown payloads" in exported["markdown"]
    assert "GateDecision" in exported["markdown"]
    assert temp_idea_spark_db.exists()


def test_pyproject_exposes_console_script():
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[project.scripts]" in text
    assert 'idea-spark = "idea_spark.cli:main"' in text


def test_file_delivery_batch_retry_and_project_binding(temp_idea_spark_db, tmp_path, capsys, monkeypatch):
    from idea_spark.tools import idea_spark_artifact_read, idea_spark_room_create
    room = json.loads(idea_spark_room_create({"title": "File review", "topic": "Evidence"}))["room_id"]
    deliveries = []
    for reviewer in ("reviewer-a", "reviewer-b"):
        assert cli.main(["files", "prepare", "--room-id", room, "--agent-id", reviewer,
            "--type", "MetaReview", "--title", "Independent review", "--round-id", "r1", "--phase", "review", "--role", "Reviewer"]) == 0
        deliveries.append(_read_stdout_json(capsys))
    complete = "# Full review\n" + "Detailed independent finding.\n" * 2000
    Path(deliveries[0]["file_path"]).write_text(complete, encoding="utf-8")
    receipts = [item["receipt_path"] for item in deliveries]
    assert cli.main(["files", "collect", *receipts]) == 1
    batch = _read_stdout_json(capsys)["deliveries"]
    assert batch[0]["success"] is True
    assert batch[1]["success"] is False
    Path(deliveries[1]["file_path"]).write_text(complete, encoding="utf-8")
    assert cli.main(["files", "collect", *receipts]) == 0
    batch = _read_stdout_json(capsys)["deliveries"]
    assert batch[0]["deduplicated"] is True
    assert batch[1]["deduplicated"] is False
    artifacts = json.loads(idea_spark_artifact_read({"room_id": room}))["artifacts"]
    assert {item["producer_agent"] for item in artifacts} == {"reviewer-a", "reviewer-b"}
    assert len(artifacts) == 2
    for artifact in artifacts:
        assert artifact["content"] == {}
        assert Path(artifact["file_path"]).read_text(encoding="utf-8") == complete
    from idea_spark.tools import idea_spark_round_wait
    barrier = json.loads(idea_spark_round_wait({"room_id": room, "round_id": "r1", "phase": "review",
        "expected_agents": ["reviewer-a", "reviewer-b"], "timeout_s": 0}))
    assert barrier["status"] == "complete"
    monkeypatch.setenv("IDEA_SPARK_DB", str(tmp_path / "other.sqlite3"))
    assert cli.main(["files", "collect", receipts[0]]) == 1
    assert "different Delphi project" in _read_stdout_json(capsys)["deliveries"][0]["error"]


def test_deep_checkpoint_collects_revisions_and_unverified_proposal(temp_idea_spark_db, tmp_path, capsys):
    from idea_spark.tools import idea_spark_artifact_link, idea_spark_room_status

    payload = _write_json(tmp_path / "room.json", {
        "room_id": "deep-cli", "title": "Deep exploration", "topic": "Method gap", "workflow_mode": "deep_exploration",
    })
    assert cli.main(["call", "idea_spark_room_create", "--json-file", str(payload)]) == 0
    room_id = _read_stdout_json(capsys)["room_id"]

    def deliver(kind, label, body):
        assert cli.main(["files", "prepare", "--room-id", room_id, "--agent-id", "worker",
                         "--type", kind, "--title", label, "--round-id", label, "--phase", "ideate"]) == 0
        receipt = _read_stdout_json(capsys)
        Path(receipt["file_path"]).write_text(body, encoding="utf-8")
        assert cli.main(["files", "collect", receipt["receipt_path"]]) == 0
        assert _read_stdout_json(capsys)["success"] is True
        return receipt

    gap = deliver("GapAnalysis", "axis", "# Gap\nA concrete method assumption fails.")
    first = deliver("IdeaCard", "C1", "# C1\nInitial mechanism.")
    revised = deliver("IdeaCard", "C2", "# C2\nA sharper transfer condition.")
    linked = json.loads(idea_spark_artifact_link({"room_id": room_id, "source_artifact_id": revised["artifact_id"],
        "target_artifact_id": first["artifact_id"], "relation": "evolves_from"}))
    assert linked["success"] is True
    assert first["file_path"] != revised["file_path"]
    assert Path(first["file_path"]).read_text() == "# C1\nInitial mechanism."
    checkpoint = _write_json(tmp_path / "checkpoint.json", {
        "phase": "review", "active_gap_artifact_id": gap["artifact_id"],
        "active_candidate_artifact_id": revised["artifact_id"], "candidate_label": "C2",
        "next_action": "review_candidate", "revision_count": 1, "pending_receipts": [],
    })
    command = ["workflow", "checkpoint", "--room-id", room_id, "--json-file", str(checkpoint)]
    assert cli.main(command) == 0
    assert _read_stdout_json(capsys)["idempotent"] is False
    assert cli.main(command) == 0
    assert _read_stdout_json(capsys)["idempotent"] is True
    status = json.loads(idea_spark_room_status({"room_id": room_id}))
    assert status["workflow_state"]["revision_count"] == 1
    assert status["workflow_state"]["active_candidate_artifact_id"] == revised["artifact_id"]

    proposal = deliver("ResearchProposal", "C2 proposal", "# Proposal\nHypothesis is unverified. Experiments are planned.")
    complete = _write_json(tmp_path / "complete.json", {"status": "completed", "final_artifact_id": proposal["artifact_id"]})
    assert cli.main(["workflow", "checkpoint", "--room-id", room_id, "--json-file", str(complete)]) == 0
    result = _read_stdout_json(capsys)
    assert result["is_terminal"] is True
    assert result["workflow_state"]["phase"] == "completed"
    status = json.loads(idea_spark_room_status({"room_id": room_id}))
    assert status["has_terminal_gate"] is False
    assert status["final_artifact_id"] == proposal["artifact_id"]
    assert status["counts"]["gates"] == 0


def test_checkpoint_invalid_completion_preserves_state_and_budget_stop_is_terminal(temp_idea_spark_db, tmp_path, capsys):
    from idea_spark.tools import idea_spark_room_create, idea_spark_room_status

    room_id = json.loads(idea_spark_room_create({"title": "Stop", "topic": "Finite budget", "workflow_mode": "deep_exploration"}))["room_id"]
    before = json.loads(idea_spark_room_status({"room_id": room_id}))
    invalid = _write_json(tmp_path / "invalid.json", {"status": "completed", "phase": "completed"})
    assert cli.main(["workflow", "checkpoint", "--room-id", room_id, "--json-file", str(invalid)]) == 1
    assert _read_stdout_json(capsys)["success"] is False
    unchanged = json.loads(idea_spark_room_status({"room_id": room_id}))
    assert unchanged["status"] == before["status"]
    assert unchanged["workflow_state"] == before["workflow_state"]
    stop = _write_json(tmp_path / "stop.json", {"status": "stopped", "stop_reason": "budget_exhausted"})
    command = ["workflow", "checkpoint", "--room-id", room_id, "--json-file", str(stop)]
    assert cli.main(command) == 0
    assert _read_stdout_json(capsys)["is_terminal"] is True
    assert cli.main(command) == 0
    assert _read_stdout_json(capsys)["idempotent"] is True
    bookkeeping = _write_json(tmp_path / "bookkeeping.json", {"handoff_path": str(tmp_path / "stage.md")})
    assert cli.main(["workflow", "checkpoint", "--room-id", room_id, "--json-file", str(bookkeeping)]) == 0
    recorded = _read_stdout_json(capsys)
    assert recorded["status"] == "stopped"
    assert recorded["workflow_state"]["handoff_path"] == str(tmp_path / "stage.md")
    reopen = _write_json(tmp_path / "reopen.json", {"status": "open"})
    assert cli.main(["workflow", "checkpoint", "--room-id", room_id, "--json-file", str(reopen)]) == 1
    assert _read_stdout_json(capsys)["success"] is False
