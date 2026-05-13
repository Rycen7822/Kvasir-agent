from __future__ import annotations

from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, payload
    return payload


def _new_quest(tmp_path: Path) -> str:
    payload = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "formal provenance", "title": "Formal Provenance"}))
    return str(payload["quest"]["quest_id"])


def _bash_runtime_files(tmp_path: Path, quest_id: str) -> list[Path]:
    quest_root = tmp_path / "CodexScientist" / "quests" / quest_id
    if not quest_root.exists():
        return []
    return [path for path in quest_root.rglob("*bash*") if path.is_file()]


def test_bash_exec_run_requires_formal_provenance_fields(tmp_path: Path):
    quest_id = _new_quest(tmp_path)
    before = _bash_runtime_files(tmp_path, quest_id)

    payload = call_tool(
        "cs_bash_exec",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "operation": "run",
            "command": "python train.py",
            "timeout_seconds": 5,
        },
    )

    assert payload.get("ok") is False, payload
    assert payload.get("error_type") == "missing_argument", payload
    missing_text = " ".join(payload.get("missing_arguments") or payload.get("missing_context_keys") or [])
    for field in ("command_class", "provenance_reason", "experiment_or_artifact_id", "cwd_policy"):
        assert field in missing_text
    assert "expected_outputs" in missing_text or "evidence_paths" in missing_text
    assert _bash_runtime_files(tmp_path, quest_id) == before


def test_bash_exec_accepts_only_formal_command_classes(tmp_path: Path):
    quest_id = _new_quest(tmp_path)
    invalid_classes = ("unit_test", "git", "package_install")

    for command_class in invalid_classes:
        payload = call_tool(
            "cs_bash_exec",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "operation": "run",
                "command": "python -c 'print(1)'",
                "command_class": command_class,
                "provenance_reason": "formal runs only",
                "experiment_or_artifact_id": "EXP-1",
                "expected_outputs": ["stdout"],
                "cwd_policy": "quest_root",
                "timeout_seconds": 5,
            },
        )

        assert payload.get("ok") is False, (command_class, payload)
        assert payload.get("error_type") == "invalid_command_class", payload

    allowed_payload = call_tool(
        "cs_bash_exec",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "operation": "run",
            "command": "python -c 'print(1)'",
            "command_class": "formal_experiment",
            "provenance_reason": "record official experiment command",
            "experiment_or_artifact_id": "EXP-2",
            "expected_outputs": ["stdout"],
            "cwd_policy": "quest_root",
            "timeout_seconds": 5,
        },
    )
    assert allowed_payload.get("error_type") != "invalid_command_class", allowed_payload
