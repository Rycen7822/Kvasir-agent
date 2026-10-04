from delegation import prepare_delegations, record_dispatch
from reconcile import reconcile_run


def test_diagnostics_preserve_host_owned_running_task(state, run):
    rid = run["run_id"]
    task = prepare_delegations(state, rid, {"tasks": [{"agent": "a", "prompt": "Long work"}]})["assignments"][0]
    record_dispatch(state, rid, task["task_id"], host_agent_id="real-host")
    with state.connect() as conn:
        conn.execute("update agent_tasks set started_at = '2000-01-01T00:00:00Z' where task_id = ?", (task["task_id"],))
    before = state.list_rows("agent_tasks", rid)
    result = reconcile_run(state, rid)
    assert result["running"][0]["task_id"] == task["task_id"]
    assert state.list_rows("agent_tasks", rid) == before
