from __future__ import annotations

import importlib.util
from pathlib import Path

from planner import plan_run
from reconcile import reconcile_run
from store import PonderForgeStore

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    spec = importlib.util.spec_from_file_location("ponder_forge_cli_reconcile_test", ROOT / "cli.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLI = _load_cli()


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def test_reconcile_marks_stale_running_task_orphan(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    start = CLI.start_run("analyze experiment metrics", profile="analysis")
    store = _store()
    plan = plan_run(store, start["run_id"])
    task = plan["tasks"][0]
    store.update_task_binding(task["task_id"], child_session_id="stale", subagent_id="sub-stale", status="running")

    result = reconcile_run(store, start["run_id"], stale_after_seconds=0)

    assert result["marked_orphan"] == [task["task_id"]]
    retry = result["delegate_task_payload_suggestion"]
    assert retry["tasks"]
    assert task["task_id"] in retry["tasks"][0]["goal"]


def test_obsolete_tool_hook_schema_adapters_are_removed():
    for rel in ("tools.py", "schemas.py", "hooks.py", "role_policy.py"):
        assert not (ROOT / rel).exists()
