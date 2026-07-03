from __future__ import annotations

import re
from typing import Any

try:
    from .gates import evaluate_gate
    from .role_policy import evaluate_role_policy
    from .schemas import HOOK_NAMES
    from .store import PonderForgeStore
except ImportError:
    from gates import evaluate_gate
    from role_policy import evaluate_role_policy
    from schemas import HOOK_NAMES
    from store import PonderForgeStore

_MARKER_RE = re.compile(r"\[PONDER_FORGE_(RUN_ID|TASK_ID|ROLE)=([^\]]+)\]")
_ROLE_BY_SESSION: dict[str, str] = {}


def parse_markers(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    found = {key.lower(): value.strip() for key, value in _MARKER_RE.findall(text)}
    return {"run_id": found.get("run_id", ""), "task_id": found.get("task_id", ""), "role": found.get("role", "")}


def on_subagent_start(**kwargs: Any) -> None:
    try:
        markers = parse_markers("\n".join(str(kwargs.get(name) or "") for name in ("goal", "context", "prompt")))
        if not markers.get("run_id") or not markers.get("task_id"):
            return None
        session_id = str(kwargs.get("session_id") or kwargs.get("child_session_id") or "")
        subagent_id = kwargs.get("subagent_id")
        store = PonderForgeStore()
        store.initialize()
        store.update_task_binding(markers["task_id"], child_session_id=session_id or None, subagent_id=str(subagent_id) if subagent_id else None, status="running")
        store.append_event(markers["run_id"], "subagent_started", {"session_id": session_id, "subagent_id": subagent_id, "role": markers.get("role")}, task_id=markers["task_id"], session_id=session_id or None)
        if session_id and markers.get("role"):
            _ROLE_BY_SESSION[session_id] = markers["role"]
    except Exception:
        return None
    return None


def on_subagent_stop(**kwargs: Any) -> None:
    try:
        store = PonderForgeStore()
        store.initialize()
        task = _task_from_kwargs(store, kwargs)
        if not task:
            return None
        reports = store.list_reports_for_task(task["task_id"])
        if reports:
            if task.get("status") != "ready_unstructured":
                store.update_task_status(task["task_id"], "finished")
            store.append_event(task["run_id"], "subagent_stopped", {"report_already_present": True}, task_id=task["task_id"], session_id=task.get("hermes_child_session_id"))
            return None
        summary = str(kwargs.get("summary") or kwargs.get("result") or "").strip()
        if summary:
            store.create_report(run_id=task["run_id"], task_id=task["task_id"], role=task["role"], title="Unstructured child summary", summary=summary, raw={"source": "subagent_stop", "precheck_only": True})
        store.update_task_status(task["task_id"], "ready_unstructured")
        store.append_event(task["run_id"], "unstructured_report_captured", {"has_summary": bool(summary)}, task_id=task["task_id"], session_id=task.get("hermes_child_session_id"))
    except Exception:
        return None
    return None


def on_post_tool_call(**kwargs: Any) -> None:
    try:
        tool_name = str(kwargs.get("tool_name") or kwargs.get("name") or "")
        if tool_name != "delegate_task":
            return None
        result = kwargs.get("result")
        store = PonderForgeStore()
        store.initialize()
        store.append_event(None, "delegate_task_observed", {"result_preview": str(result)[:1000]})
    except Exception:
        return None
    return None


def on_pre_tool_call(**kwargs: Any) -> dict | None:
    try:
        session_id = str(kwargs.get("session_id") or "")
        tool_name = str(kwargs.get("tool_name") or kwargs.get("name") or "")
        role = _ROLE_BY_SESSION.get(session_id)
        if not role and session_id:
            store = PonderForgeStore()
            store.initialize()
            task = store.get_task_by_session(session_id)
            role = str(task.get("role")) if task else ""
        if not role:
            return None
        return evaluate_role_policy(role, tool_name)
    except Exception:
        return None


def on_pre_llm_call(**kwargs: Any) -> dict | None:
    try:
        run_id = kwargs.get("run_id")
        if not run_id:
            return None
        store = PonderForgeStore()
        store.initialize()
        run = store.get_run(str(run_id))
        if not run:
            return None
        gate = evaluate_gate(store, str(run_id))
        reports = len(store.list_rows("reports", str(run_id)))
        content = "\n".join(
            [
                "[Ponder-Forge status]",
                f"run_id={run_id}",
                f"profile={run['profile']}",
                f"state={run['status']}",
                f"ready_reports={reports}",
                f"unverified_critical_assertions={gate['metrics']['critical_assertion_count'] - gate['metrics']['accepted_critical_assertion_count']}",
                "unresolved_conflicts=0",
                f"next_required_action={'ponder_forge_finalize' if gate['finalize_allowed'] else 'ponder_forge_verify'}",
                f"finalize_allowed={str(gate['finalize_allowed']).lower()}",
            ]
        )
        return {"role": "system", "content": content}
    except Exception:
        return None


def on_session_end(**kwargs: Any) -> None:
    try:
        session_id = str(kwargs.get("session_id") or "")
        if session_id:
            _ROLE_BY_SESSION.pop(session_id, None)
    except Exception:
        return None
    return None


def _task_from_kwargs(store: PonderForgeStore, kwargs: dict[str, Any]) -> dict | None:
    markers = parse_markers("\n".join(str(kwargs.get(name) or "") for name in ("goal", "context", "summary", "result")))
    if markers.get("task_id"):
        return store.get_task(markers["task_id"])
    session_id = str(kwargs.get("session_id") or kwargs.get("child_session_id") or "")
    if session_id:
        return store.get_task_by_session(session_id)
    return None


HOOK_HANDLERS = {
    "subagent_start": on_subagent_start,
    "subagent_stop": on_subagent_stop,
    "post_tool_call": on_post_tool_call,
    "pre_tool_call": on_pre_tool_call,
    "pre_llm_call": on_pre_llm_call,
    "on_session_end": on_session_end,
}

assert set(HOOK_HANDLERS) == set(HOOK_NAMES)
