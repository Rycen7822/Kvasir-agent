"""Ponder's full high/max workflow through native assignments and durable files."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import uuid

from delphi.mcp import check_fields, next_call, templates, text, worker_delivery, write_json
from .delegation import prepare_delegations, record_dispatch, report_content
from .planner import plan_run
from .profiles import select_profile
from .renderer import render_final_report
from .report_ingest import ingest_report
from .store import PonderForgeStore
from .strategy import coordinator_prompt, team_effort
from .swarm import normalize_swarm_budget
from .verifier import verify_run


def _store() -> PonderForgeStore:
    return PonderForgeStore()


def _run(run_id: str) -> dict:
    store = _store()
    if not store.db_path.exists():
        raise ValueError("No Ponder state; use action=open")
    run = store.get_run(run_id)
    if not run:
        raise ValueError("unknown run_id")
    return run


def validate(args: dict, payload: dict) -> None:
    action = args["action"]
    if action == "open":
        text(args["goal"], "goal")
        args.setdefault("effort", "max")
        check_fields(payload, {"profile", "constraints", "budget"})
        select_profile(args["goal"], requested=payload.get("profile", "auto"))
        normalize_swarm_budget(payload.get("budget"))
        if not isinstance(payload.get("constraints", ""), str):
            raise ValueError("constraints must be text")
        return
    _run(args["run_id"])
    if action == "prepare":
        check_fields(payload, {"tasks"}, {"tasks"})
        if not isinstance(payload["tasks"], list) or not 1 <= len(payload["tasks"]) <= 20:
            raise ValueError("prepare requires 1 to 20 assignments")
    elif action == "verify":
        check_fields(payload, {"mode", "draft_path", "conflict", "report_ids", "task_ids"})
        if payload.get("mode", "final") == "final":
            text(payload.get("draft_path"), "draft_path")
            # This is allocation input, not a file checksum: reserve the exact
            # answer assigned to this verifier and reject changed-request reuse.
            payload["draft"] = text(Path(payload["draft_path"]).read_text(encoding="utf-8"), "complete draft")
        elif payload.get("mode") != "local":
            raise ValueError("verification mode must be final or local")
    elif action == "record":
        if args["status"] not in {"started", "cancelled"}:
            raise ValueError("record status must be started or cancelled")
        if args["status"] == "started":
            text(args.get("host_agent_id"), "host_agent_id")
        elif "host_agent_id" in args:
            raise ValueError("cancelled record omits host_agent_id")
    elif action == "finish":
        if args.get("status", "completed") not in {"completed", "partial"}:
            raise ValueError("finish status must be completed or partial")
        check_fields(payload, {"reason"})
        if args.get("status") == "partial":
            text(payload.get("reason"), "partial reason")
        elif payload:
            raise ValueError("reason is only used for partial finish")
        text(Path(args["file_path"]).read_text(encoding="utf-8"), "complete final draft")


def _contracts(run_id: str) -> dict:
    return templates(_store().run_dir(run_id), {
        "plan": {"tasks": [{"description": "Sub-question", "owners": [], "resolution": "open"}]},
        "prepare": {"tasks": [{"agent": "researcher", "system_prompt": "", "prompt": "Focused work", "task_ids": []}]},
        "verify": {"mode": "final", "draft_path": "/absolute/project/draft.md"},
        "local_verify": {"mode": "local", "conflict": "Specific conflict", "report_ids": []},
        "partial_finish": {"reason": "Observed interruption or budget exhaustion"},
        "collect_metadata": {"status": "finished"},
    })


def _delivery(task_id: str) -> Path:
    return _store().state_dir / "deliveries" / task_id


def _assignments(args: dict, result: dict) -> dict:
    assignments = []
    for item in result["assignments"]:
        directory = _delivery(item["task_id"])
        output, receipt = directory / "result.md", directory / "receipt.json"
        data = {"version": 1, "db_path": str(_store().db_path), "run_id": args["run_id"],
                "task_id": item["task_id"], "report_id": "report_" + item["task_id"],
                "file_path": str(output), "status": "finished"}
        if not receipt.exists():
            write_json(receipt, data)
        scratch = Path(args["project"]) / ".work/delphi" / item["task_id"]
        instructions = worker_delivery(item["system_prompt"] + "\n\n" + item["prompt"], output, scratch)
        assignments.append({"task_id": item["task_id"], "agent": item["agent"], "task_ids": item["task_ids"],
                            "instructions": instructions, "file_path": str(output), "receipt_path": str(receipt),
                            "scratch_path": str(scratch)})
    return {"run_id": args["run_id"], "assignments": assignments, "execution_owner": "native_host",
            "instruction": "Launch with native tools, record only confirmed starts, then wait and collect complete files. A retry does not authorize redispatch.",
            "next_call": next_call(args, "collect", receipt_paths=[x["receipt_path"] for x in assignments])}


def _status(args: dict) -> dict:
    run = _run(args["run_id"])
    store, limit = _store(), args.get("limit", 20)
    with sqlite3.connect(store.db_path.as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        board = [dict(x) for x in conn.execute("select node_id, status, input_json from workflow_nodes "
                                             "where run_id=? and node_type='research_task'", (args["run_id"],))]
        tasks = [dict(x) for x in conn.execute("select task_id, role, status, hermes_subagent_id as host_agent_id from agent_tasks "
            "where run_id=? order by case when status in ('queued','running') then 0 else 1 end, rowid desc", (args["run_id"],))]
        reports = [dict(x) for x in conn.execute("select report_id, task_id, role, title, confidence from reports "
                                               "where run_id=? order by rowid desc", (args["run_id"],))]
        if args.get("task_id") and not any(x["task_id"] == args["task_id"] for x in tasks):
            raise ValueError("task_id does not belong to this run")
        selected = [x for x in reports if not args.get("task_id") or x["task_id"] == args["task_id"]][:limit]
        for item in selected:
            path = store.state_dir / "reports" / (item["report_id"] + ".md")
            if not path.exists():
                row = conn.execute("select * from reports where report_id=?", (item["report_id"],)).fetchone()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(report_content(dict(row)), encoding="utf-8")
            item["file_path"] = str(path)
            item["title"] = (item["title"] or "")[:160]
            item["role"] = item["role"][:160]
    questions = [{"id": x["node_id"], "resolution": x["status"], **json.loads(x["input_json"])} for x in board]
    history = store.run_dir(args["run_id"]) / "history-index.json"
    write_json(history, {"task_board": questions, "assignments": tasks, "reports": reports})
    visible_tasks = [x for x in tasks if not args.get("task_id") or x["task_id"] == args["task_id"]]
    counts = {status: sum(x["status"] == status for x in tasks) for status in {x["status"] for x in tasks}}
    return {"run_id": args["run_id"], "status": run["status"], "effort": team_effort(run), "task_counts": counts,
            "task_board": [{**x, "description": x["description"][:200], "notes": x.get("notes", "")[:200],
                            "owners": [name[:160] for name in x.get("owners", [])[:limit]]} for x in questions[:limit]],
            "assignments": [{**x, "role": x["role"][:160], "host_agent_id": (x["host_agent_id"] or "")[:1024] or None}
                            for x in visible_tasks[:limit]], "reports": selected,
            "has_more": max(len(questions), len(visible_tasks), len(reports)) > limit,
            "history_index_path": str(history), "database_path": str(store.db_path),
            "final_file_path": str(store.run_dir(args["run_id"]) / "final.md") if run.get("final_report_md") else None}


def _collect(args: dict, payload: dict) -> dict:
    check_fields(payload, {"status", "title", "confidence"})
    store = _store()
    if args.get("receipt_paths"):
        deliveries = []
        for name in args["receipt_paths"]:
            try:
                receipt = json.loads(Path(name).read_text(encoding="utf-8"))
                if receipt.get("version") != 1 or receipt.get("db_path") != str(store.db_path) or receipt.get("run_id") != args["run_id"]:
                    raise ValueError("receipt belongs to another project/run or has an unsupported version")
                data = {**{key: value for key, value in args.items() if key != "receipt_paths"},
                        "task_id": receipt["task_id"], "file_path": receipt["file_path"]}
                meta = {key: receipt[key] for key in ("status", "title", "confidence") if key in receipt}
                result = _collect(data, meta)
                deliveries.append({"receipt_path": name, **result})
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                deliveries.append({"receipt_path": name, "ok": False, "error": str(exc)[:240]})
        return {"ok": all(x.get("ok", True) for x in deliveries), "run_id": args["run_id"], "deliveries": deliveries}
    content = text(Path(args["file_path"]).read_text(encoding="utf-8"), "complete report")
    result = ingest_report(store, {**payload, "run_id": args["run_id"], "task_id": args["task_id"],
        "report_id": "report_" + args["task_id"], "status": args.get("status", payload.get("status", "finished")), "content": content})
    path = store.state_dir / "reports" / (result["report_id"] + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"ok": True, **result, "file_path": str(path), "next_call": next_call(args, "status")}


def dispatch(args: dict, payload: dict, identities: dict) -> dict:
    store, action = _store(), args["action"]
    if action == "open":
        store.initialize()
        run = store.get_run(identities["run_id"])
        if not run:
            run = store.create_run(args["goal"], select_profile(args["goal"], requested=payload.get("profile", "auto")),
                budget=normalize_swarm_budget(payload.get("budget")).as_dict(),
                config={"constraints": payload.get("constraints", ""), "team_effort": args["effort"]}, run_id=identities["run_id"])
        bound = {**args, "run_id": run["run_id"]}
        policy = store.run_dir(run["run_id"]) / "controller.md"
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text(coordinator_prompt(run, mcp_project=args["project"]), encoding="utf-8")
        paths = _contracts(run["run_id"])
        return {"run_id": run["run_id"], "status": run["status"], "effort": team_effort(run), "profile": run["profile"],
                "instruction_path": str(policy), "input_templates": paths,
                "instruction": "Read the complete controller policy once, then edit the plan template and use next_call.",
                "next_call": next_call(bound, "plan", input_path=paths["plan"])}
    if action == "status":
        return _status(args)
    if action == "plan":
        check_fields(payload, {"tasks"}, {"tasks"})
        result = plan_run(store, args["run_id"], payload)
        path = store.run_dir(args["run_id"]) / "task-board.json"
        write_json(path, result["task_board"])
        return {"run_id": args["run_id"], "task_board": result["task_board"][:20], "task_board_path": str(path),
                "next_call": next_call(args, "prepare", input_path=_contracts(args["run_id"])["prepare"], request_id="req_" + uuid.uuid4().hex)}
    if action == "prepare":
        return _assignments(args, prepare_delegations(store, args["run_id"], payload, allocation_ids=identities["task_ids"]))
    if action == "record":
        return record_dispatch(store, args["run_id"], args["task_id"], host_agent_id=args.get("host_agent_id"), cancelled=args["status"] == "cancelled")
    if action == "collect":
        return _collect(args, payload)
    if action == "verify":
        spec = dict(payload)
        if spec.get("mode", "final") == "final":
            spec.pop("draft_path")
        return _assignments(args, verify_run(store, args["run_id"], spec, allocation_ids=identities["task_ids"]))
    if action == "finish":
        result = render_final_report(store, args["run_id"], Path(args["file_path"]).read_text(encoding="utf-8"),
                                     partial=args.get("status") == "partial", reason=payload.get("reason", ""))
        return {key: value for key, value in result.items() if key != "final_report_md"}
    raise ValueError("unsupported Ponder action")
