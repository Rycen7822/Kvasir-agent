from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hooks_module = _load_module("hooks.py", "ponder_forge_hooks_test")
tools_module = _load_module("tools.py", "ponder_forge_tools_hooks_test")
store_module = _load_module("store.py", "ponder_forge_store_hooks_test")
HANDLERS = tools_module.HANDLERS
PonderForgeStore = store_module.PonderForgeStore


def _call(name: str, args: dict) -> dict:
    return json.loads(HANDLERS[name](args))


def _task_goal(start: dict, task: dict) -> str:
    return f"[PONDER_FORGE_RUN_ID={start['run_id']}] [PONDER_FORGE_TASK_ID={task['task_id']}] [PONDER_FORGE_ROLE={task['role']}] {task['goal']}"


def test_hook_names_include_session_end_and_register_handlers():
    schemas = _load_module("schemas.py", "ponder_forge_schemas_hooks_test")
    assert "on_session_end" in schemas.HOOK_NAMES
    assert set(hooks_module.HOOK_HANDLERS) == set(schemas.HOOK_NAMES)


class BrokenStore(PonderForgeStore):
    def update_task_binding(self, *args, **kwargs):  # pragma: no cover - called by hook
        raise RuntimeError("db down")


def test_hooks_fail_open_on_store_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(hooks_module, "PonderForgeStore", BrokenStore)

    result = hooks_module.on_subagent_start(goal="[PONDER_FORGE_RUN_ID=x] [PONDER_FORGE_TASK_ID=y] [PONDER_FORGE_ROLE=z]", session_id="child")

    assert result is None


def test_subagent_start_binds_task_and_role_policy_blocks_finalize(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = _call("ponder_forge_start", {"goal": "fix pytest failure", "profile": "auto"})
    plan = _call("ponder_forge_plan", {"run_id": start["run_id"]})
    task = plan["tasks"][0]

    hooks_module.on_subagent_start(goal=_task_goal(start, task), session_id="child-1", subagent_id="sub-1")
    store = PonderForgeStore()
    updated = [row for row in store.list_rows("agent_tasks", start["run_id"]) if row["task_id"] == task["task_id"]][0]

    assert updated["status"] == "running"
    assert updated["hermes_child_session_id"] == "child-1"
    block = hooks_module.on_pre_tool_call(tool_name="ponder_forge_finalize", session_id="child-1")
    assert block["action"] == "block"
    assert "cannot mutate files or finalize" in block["message"]
    assert hooks_module.on_pre_tool_call(tool_name="ponder_forge_report_submit", session_id="child-1") is None
    assert hooks_module.on_pre_tool_call(tool_name="ponder_forge_finalize", session_id="ordinary-session") is None


def test_subagent_stop_captures_unstructured_report_once(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = _call("ponder_forge_start", {"goal": "research source notes", "profile": "research"})
    plan = _call("ponder_forge_plan", {"run_id": start["run_id"]})
    task = plan["tasks"][0]
    hooks_module.on_subagent_start(goal=_task_goal(start, task), session_id="child-2", subagent_id="sub-2")

    hooks_module.on_subagent_stop(session_id="child-2", summary="raw child summary")
    hooks_module.on_subagent_stop(session_id="child-2", summary="raw child summary again")
    store = PonderForgeStore()
    reports = store.list_rows("reports", start["run_id"])
    updated = [row for row in store.list_rows("agent_tasks", start["run_id"]) if row["task_id"] == task["task_id"]][0]

    assert updated["status"] == "ready_unstructured"
    assert len(reports) == 1
    assert reports[0]["summary"] == "raw child summary"


def test_reconcile_marks_stale_running_task_orphan(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = _call("ponder_forge_start", {"goal": "analyze experiment metrics", "profile": "analysis"})
    plan = _call("ponder_forge_plan", {"run_id": start["run_id"]})
    task = plan["tasks"][0]
    store = PonderForgeStore()
    store.update_task_binding(task["task_id"], child_session_id="stale", subagent_id="sub-stale", status="running")

    result = _call("ponder_forge_reconcile", {"run_id": start["run_id"], "stale_after_seconds": 0})

    assert result["success"] is True
    assert result["marked_orphan"] == [task["task_id"]]
    retry = result["delegate_task_payload_suggestion"]
    assert retry["tasks"]
    assert task["task_id"] in retry["tasks"][0]["goal"]


def test_pre_llm_call_injects_compact_status_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = _call("ponder_forge_start", {"goal": "fix pytest failure", "profile": "coding"})
    _call("ponder_forge_plan", {"run_id": start["run_id"]})

    injected = hooks_module.on_pre_llm_call(run_id=start["run_id"])

    assert injected["role"] == "system"
    assert "[Ponder-Forge status]" in injected["content"]
    assert "finalize_allowed=false" in injected["content"]
    assert "evidence_items" not in injected["content"]
