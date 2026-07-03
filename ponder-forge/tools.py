from __future__ import annotations

import json
from typing import Any, Callable

try:
    from .delegation import prepare_delegations
    from .gates import evaluate_gate, supported_critical_assertion_ids
    from .planner import plan_run
    from .profiles import select_profile
    from .reconcile import reconcile_run
    from .renderer import render_final_report
    from .report_ingest import ingest_report
    from .schemas import TOOL_NAMES
    from .store import PonderForgeStore
    from .verifier import verify_run
except ImportError:
    from delegation import prepare_delegations
    from gates import evaluate_gate, supported_critical_assertion_ids
    from planner import plan_run
    from profiles import select_profile
    from reconcile import reconcile_run
    from renderer import render_final_report
    from report_ingest import ingest_report
    from schemas import TOOL_NAMES
    from store import PonderForgeStore
    from verifier import verify_run

JsonDict = dict[str, Any]
Handler = Callable[..., str]


def _json(payload: JsonDict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _ok(payload: JsonDict | None = None) -> str:
    return _json({"success": True, **(payload or {})})


def _err(message: str, **extra: Any) -> str:
    return _json({"success": False, "error": message, **extra})


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def _final_artifact_paths(store: PonderForgeStore, run_id: str) -> JsonDict:
    run_dir = store.run_dir(run_id)
    return {
        "final_md": str(run_dir / "final.md"),
        "graph_json": str(run_dir / "graph.json"),
        "verdicts_json": str(run_dir / "verdicts.json"),
        "pool_status_json": str(run_dir / "pool_status.json"),
    }


def _completed_final_payload(store: PonderForgeStore, run: JsonDict) -> JsonDict | None:
    if run.get("status") != "completed" or not run.get("final_report_md"):
        return None
    return {
        "status": "final",
        "run_id": str(run["run_id"]),
        "final_report_markdown": str(run["final_report_md"]),
        "artifact_paths": _final_artifact_paths(store, str(run["run_id"])),
        "idempotent": True,
    }


def _require(args: dict | None, *names: str) -> str | None:
    data = args or {}
    for name in names:
        if data.get(name) in (None, ""):
            return name
    return None


def _coerce_args(args: dict | None = None, kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Accept both direct tool kwargs and legacy single-dict handler calls.

    Hermes plugin tools are advertised with ``additionalProperties: true`` and
    can be invoked by the runtime as ``handler(**tool_args)``. Unit tests and
    internal benchmark helpers call handlers as ``handler(args_dict)``. Keep
    both paths working, and also tolerate an explicit ``{"args": {...}}``
    wrapper from agents working around older handler signatures.
    """

    data = dict(args or {})
    extra = dict(kwargs or {})
    nested = extra.pop("args", None)
    if isinstance(nested, dict):
        data.update(nested)
    elif nested is not None:
        data["args"] = nested
    data.update(extra)
    return data


def ponder_forge_start(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "goal")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        profile = select_profile(str(args["goal"]), requested=str(args.get("profile") or "auto"))
        run = _store().create_run(
            goal=str(args["goal"]),
            profile=profile,
            budget=args.get("budget") or {},
            config={"constraints": args.get("constraints") or []},
            parent_session_id=args.get("parent_session_id"),
        )
        return _ok({"ok": True, "run_id": run["run_id"], "profile": profile, "status": run["status"], "next_tool": "ponder_forge_plan"})
    except Exception as exc:
        return _err(str(exc))


def ponder_forge_plan(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "run_id")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        return _ok(plan_run(_store(), str((args or {})["run_id"])))
    except Exception as exc:
        return _err(str(exc))


def ponder_forge_prepare_delegations(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "run_id")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        return _ok(prepare_delegations(_store(), str((args or {})["run_id"])))
    except Exception as exc:
        return _err(str(exc))


def ponder_forge_report_submit(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "run_id", "role", "summary")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        store = _store()
        run_id = str((args or {})["run_id"])
        run = store.get_run(run_id)
        if run and run.get("status") == "completed":
            return _err("run is already completed; report submission is closed", run_id=run_id, status="completed")
        result = ingest_report(store, args or {})
        task_id = (args or {}).get("task_id")
        if task_id:
            store.update_task_status(str(task_id), "finished")
        return _ok(result)
    except Exception as exc:
        return _err(str(exc))


def ponder_forge_pool_status(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "run_id")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        store = _store()
        run_id = str((args or {})["run_id"])
        counts = {table: len(store.list_rows(table, run_id)) for table in ("agent_tasks", "reports", "assertions", "evidence_items", "artifacts")}
        gate = evaluate_gate(store, run_id)
        return _ok({"run_id": run_id, "counts": counts, "gate_status": gate["status"], "next_required_action": "ponder_forge_finalize" if gate["finalize_allowed"] else "ponder_forge_verify"})
    except Exception as exc:
        return _err(str(exc))


def ponder_forge_verify(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "run_id")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        store = _store()
        run_id = str((args or {})["run_id"])
        return _ok(verify_run(store, run_id, args or {}))
    except Exception as exc:
        return _err(str(exc))


def ponder_forge_gate_status(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "run_id")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        return _ok(evaluate_gate(_store(), str((args or {})["run_id"])))
    except Exception as exc:
        return _err(str(exc))


def ponder_forge_finalize(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "run_id")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        store = _store()
        run_id = str((args or {})["run_id"])
        run = store.get_run(run_id)
        if run:
            completed = _completed_final_payload(store, run)
            if completed:
                return _ok(completed)
        gate = evaluate_gate(store, run_id)
        if not gate["finalize_allowed"]:
            return _ok({"status": "blocked", "reason": "profile_gate_failed", "gaps": gate["gaps"], "instruction": "Continue Ponder-Forge. Do not produce final answer."})
        for assertion_id in supported_critical_assertion_ids(store, run_id):
            store.update_assertion_status(assertion_id, "accepted")
        return _ok(render_final_report(store, run_id))
    except Exception as exc:
        return _err(str(exc))


def ponder_forge_reconcile(args: dict | None = None, **kwargs: Any) -> str:
    args = _coerce_args(args, kwargs)
    missing = _require(args, "run_id")
    if missing:
        return _err(f"missing required field: {missing}")
    try:
        stale_after_seconds = int((args or {}).get("stale_after_seconds", 1800))
        return _ok(reconcile_run(_store(), str((args or {})["run_id"]), stale_after_seconds=stale_after_seconds))
    except Exception as exc:
        return _err(str(exc))


HANDLERS: dict[str, Handler] = {
    "ponder_forge_start": ponder_forge_start,
    "ponder_forge_plan": ponder_forge_plan,
    "ponder_forge_prepare_delegations": ponder_forge_prepare_delegations,
    "ponder_forge_report_submit": ponder_forge_report_submit,
    "ponder_forge_pool_status": ponder_forge_pool_status,
    "ponder_forge_verify": ponder_forge_verify,
    "ponder_forge_gate_status": ponder_forge_gate_status,
    "ponder_forge_finalize": ponder_forge_finalize,
    "ponder_forge_reconcile": ponder_forge_reconcile,
}

assert set(HANDLERS) == set(TOOL_NAMES)
