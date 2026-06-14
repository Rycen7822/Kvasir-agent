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
