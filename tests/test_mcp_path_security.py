from __future__ import annotations

from codex_scientist.mcp.tool_registry import call_tool


def test_trial_show_rejects_path_traversal_id(tmp_path):
    outside = tmp_path / "outside" / "trial.json"
    outside.parent.mkdir(parents=True)
    outside.write_text('{"trial_id":"owned","status":"kept"}', encoding="utf-8")

    payload = call_tool("cs_trial_show", {"project": str(tmp_path), "trial_id": "../../outside"})

    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_trial_id"
    assert "trial" not in payload


def test_runner_status_rejects_path_traversal_id(tmp_path):
    outside = tmp_path / "outside" / "runner.json"
    outside.parent.mkdir(parents=True)
    outside.write_text('{"run_id":"owned","status":"completed"}', encoding="utf-8")

    payload = call_tool("cs_runner_status", {"project": str(tmp_path), "run_id": "../../outside"})

    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_run_id"
    assert "run" not in payload
