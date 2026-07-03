from __future__ import annotations

import json
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_tools():
    spec = importlib.util.spec_from_file_location("ponder_forge_tools_delegation_test", ROOT / "tools.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HANDLERS = _load_tools().HANDLERS


def _call(name: str, args: dict) -> dict:
    return json.loads(HANDLERS[name](args))


def test_prepare_delegations_returns_native_delegate_task_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = _call(
        "ponder_forge_start",
        {
            "goal": "fix failing pytest in store.py using project alpha context",
            "profile": "auto",
            "budget": {"max_tasks_per_wave": 2},
            "constraints": ["do not modify external fixture alpha"],
        },
    )
    plan = _call("ponder_forge_plan", {"run_id": start["run_id"]})

    prepared = _call("ponder_forge_prepare_delegations", {"run_id": start["run_id"]})

    assert prepared["success"] is True
    assert prepared["native_tool_to_call_next"] == "delegate_task"
    payload = prepared["delegate_task_payload"]
    assert set(payload) == {"tasks"}
    assert len(payload["tasks"]) == len(plan["tasks"]) == 2
    for task in payload["tasks"]:
        assert set(task) == {"goal", "context", "role"}
        assert task["role"] == "leaf"
        assert "toolsets" not in task
        assert "[PONDER_FORGE_RUN_ID=" in task["goal"]
        assert "[PONDER_FORGE_TASK_ID=" in task["goal"]
        assert "[PONDER_FORGE_ROLE=" in task["goal"]
        assert "[PONDER_FORGE_PROFILE=coding]" in task["context"]
        assert "project alpha context" in task["context"]
        assert "do not modify external fixture alpha" in task["context"]
        assert "ponder_forge_report_submit" in task["context"]


def test_prepare_delegations_is_idempotent_for_queued_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = _call("ponder_forge_start", {"goal": "analyze csv metrics", "profile": "auto", "budget": {"max_tasks_per_wave": 1}})
    _call("ponder_forge_plan", {"run_id": start["run_id"]})

    first = _call("ponder_forge_prepare_delegations", {"run_id": start["run_id"]})
    second = _call("ponder_forge_prepare_delegations", {"run_id": start["run_id"]})

    assert first["delegate_task_payload"] == second["delegate_task_payload"]


def test_prepare_delegations_exposes_analysis_metric_command_requirement(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = _call("ponder_forge_start", {"goal": "analyze csv metrics", "profile": "analysis"})
    _call("ponder_forge_plan", {"run_id": start["run_id"]})

    prepared = _call("ponder_forge_prepare_delegations", {"run_id": start["run_id"]})

    contexts = [task["context"] for task in prepared["delegate_task_payload"]["tasks"]]
    assert contexts
    assert all("metric_output" in context and "command" in context for context in contexts)
