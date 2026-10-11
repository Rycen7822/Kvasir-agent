"""Idea-Spark's file-first operations on the shared Delphi MCP entrypoint."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import uuid

from delphi.mcp import check_fields, next_call, templates, text, worker_delivery, write_json
from .file_delivery import collect_files, prepare_file
from .schemas import ARTIFACT_TYPES
from .store import IdeaSparkStore
from . import tools
from .workflow import DEEP_EXPLORATION, MODE_REFERENCES, OPEN_DISCUSSION, WORKFLOW_MODES, save_checkpoint, workflow_mode

_REFERENCES = Path(__file__).parent / "resources/skills/idea-spark-usage/references"
_ROLE_FILES = {"gapfinder": "gap-finder.md", "innovator": "innovator.md", "reviewer": "reviewer.md",
               "reader": "reader.md", "proposalwriter": "proposal-writer.md"}


def _call(handler, payload: dict) -> dict:
    result = json.loads(handler(payload))
    if not result.get("success"):
        raise ValueError(result.get("error", "Idea-Spark operation failed"))
    return result


def _room(room_id: str) -> dict:
    db = IdeaSparkStore().db_path
    if not db.exists():
        raise ValueError("No Idea-Spark state; use action=open")
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("select * from rooms where room_id=?", (room_id,)).fetchone()
    if not row:
        raise ValueError("unknown room_id")
    return dict(row)


def validate(args: dict, payload: dict) -> None:
    action = args["action"]
    if action == "open":
        text(args["goal"], "goal")
        args.setdefault("mode", OPEN_DISCUSSION)
        workflow_mode({"workflow_mode": args["mode"]})
        check_fields(payload, {"title", "expected_agents", "framing"})
        if "title" in payload:
            text(payload["title"], "title")
        if "expected_agents" in payload and (not isinstance(payload["expected_agents"], list)
                or any(not isinstance(x, str) or not x.strip() for x in payload["expected_agents"])):
            raise ValueError("expected_agents must be a list of nonempty names")
        if "framing" in payload and not isinstance(payload["framing"], dict):
            raise ValueError("framing must be an object")
        return
    room = _room(args["room_id"])
    if action == "prepare":
        if room["status"] in {"gated", "completed", "stopped"}:
            raise ValueError("room is closed; create another room for new work")
        check_fields(payload, {"task", "title", "artifact_type", "inputs", "phase", "round_id", "summary"},
                     {"task", "title", "artifact_type"})
        for key in ("task", "title", "artifact_type"):
            text(payload[key], key)
        if payload["artifact_type"] not in ARTIFACT_TYPES:
            raise ValueError("unsupported artifact_type")
        if not isinstance(payload.get("inputs", []), list) or any(not isinstance(x, str) for x in payload.get("inputs", [])):
            raise ValueError("inputs must be a list of file paths")
        for key in ("phase", "round_id", "summary"):
            if key in payload and not isinstance(payload[key], str):
                raise ValueError(f"{key} must be text")


def _directory(room_id: str) -> Path:
    return IdeaSparkStore().db_path.parent / "rooms" / room_id


def _contracts(room_id: str, mode: str) -> dict:
    finish = ({"gate_type": "overall", "decision": "needs_more_evidence", "rationale": "Parent decision",
               "input_artifact_ids": [], "created_by": "parent"}
              if mode == OPEN_DISCUSSION else {"status": "stopped", "stop_reason": "Parent stop reason"})
    return templates(_directory(room_id), {
        "prepare": {"task": "Focused research task", "title": "Complete report", "artifact_type": "MetaReview",
                    "inputs": [], "phase": "review", "round_id": "r1"},
        "update": {"checkpoint": {"phase": "review", "next_action": "Parent's next decision"}},
        "finish": finish,
    })


def _status(args: dict) -> dict:
    room = _room(args["room_id"])
    metadata = json.loads(room["metadata_json"])
    mode = workflow_mode(metadata)
    limit = args.get("limit", 20)
    db = IdeaSparkStore().db_path
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        artifacts = [dict(x) for x in conn.execute(
            "select artifact_id, artifact_type, producer_agent, title, file_path, status from artifacts "
            "where room_id=? order by rowid desc", (args["room_id"],))]
        counts = {name: conn.execute(f"select count(*) from {name} where room_id=?", (args["room_id"],)).fetchone()[0]
                  for name in ("artifacts", "messages", "gates", "open_needs")}
        gate = conn.execute("select gate_id, gate_type, decision from gates where room_id=? order by rowid desc limit 1",
                            (args["room_id"],)).fetchone()
    index = _directory(args["room_id"]) / "artifact-index.json"
    write_json(index, artifacts)
    state = metadata.get("workflow_state", {})
    visible = {key: (value[:200] if isinstance(value, str) else value[:limit] if isinstance(value, list) else value)
               for key, value in state.items() if key in {
                   "phase", "candidate_label", "next_action", "revision_count", "pending_receipts", "next_inputs",
                   "active_gap_artifact_id", "active_candidate_artifact_id", "final_artifact_id", "stop_reason"}}
    selected = [{**item, "title": (item["title"] or "")[:160], "producer_agent": item["producer_agent"][:160]}
                for item in artifacts[:limit]]
    final = next((x["file_path"] for x in artifacts if x["artifact_id"] == state.get("final_artifact_id")), None)
    return {"room_id": args["room_id"], "mode": mode, "status": room["status"], "checkpoint": visible,
            "counts": counts, "artifacts": selected, "has_more": len(artifacts) > limit,
            "artifact_index_path": str(index), "database_path": str(db), "final_file_path": final,
            "latest_gate": dict(gate) if gate else None,
            "is_terminal": room["status"] in {"gated", "completed", "stopped"}}


def dispatch(args: dict, payload: dict, identities: dict) -> dict:
    action = args["action"]
    if action == "open":
        room_id = identities["room_id"]
        store = IdeaSparkStore()
        store.initialize()
        with store.connect() as conn:
            exists = conn.execute("select 1 from rooms where room_id=?", (room_id,)).fetchone()
        if not exists:
            _call(tools.idea_spark_room_create, {"room_id": room_id, "title": payload.get("title", args["goal"][:120]),
                  "topic": args["goal"], "workflow_mode": args["mode"], "metadata": payload})
        bound = {**args, "room_id": room_id}
        paths = _contracts(room_id, args["mode"])
        policy = _directory(room_id) / "controller.md"
        policy.write_text((_REFERENCES / "modes" / MODE_REFERENCES[args["mode"]]).read_text(encoding="utf-8")
                          .replace("../roles/", str(_REFERENCES / "roles") + "/")
                          .replace("`idea_spark_gate_record`", "`ka_delphi(action=finish)`")
                          + "\n\n# MCP operations\nUse ka_delphi with workflow=idea_spark. "
                          "Prepare complete files, launch/wait through native host tools, collect receipt_paths, "
                          "then update parent checkpoints. Finish uses the supplied mode-specific input template. "
                          "Open discussion's gate_record is performed by action=finish. "
                          "Read the complete selected policy and referenced role instructions. "
                          "Parent decisions and native completion are separate; finite budgets permit stopping.\n",
                          encoding="utf-8")
        return {"room_id": room_id, "mode": args["mode"], "status": "open", "supported_modes": list(WORKFLOW_MODES), "default_mode": OPEN_DISCUSSION,
                "instruction_path": str(policy), "input_templates": paths,
                "instruction": "Read instruction_path, edit the prepare template, then use next_call. Read only selected role references.",
                "next_call": next_call(bound, "prepare", agent_id="reviewer-1", input_path=paths["prepare"], request_id="req_" + uuid.uuid4().hex)}
    if action == "status":
        return _status(args)
    mode = workflow_mode(json.loads(_room(args["room_id"])["metadata_json"]))
    if action == "prepare":
        receipt = prepare_file(SimpleNamespace(room_id=args["room_id"], agent_id=args["agent_id"],
            title=payload["title"], artifact_type=payload["artifact_type"], role=args.get("role", ""),
            phase=payload.get("phase", ""), round_id=payload.get("round_id", ""), summary=payload.get("summary", "")),
            artifact_id=identities["artifact_id"])
        inputs = [str(Path(x).expanduser().resolve()) for x in payload.get("inputs", [])]
        instructions = f"Role: {args.get('role', args['agent_id'])}\nTask: {payload['task']}\nInput files: {json.dumps(inputs)}"
        role_key = args.get("role", "").lower().replace(" ", "").replace("_", "").replace("-", "")
        if mode == DEEP_EXPLORATION and role_key in _ROLE_FILES:
            instructions = (_REFERENCES / "roles" / _ROLE_FILES[role_key]).read_text(encoding="utf-8") + "\n\n" + instructions
        scratch = Path(args["project"]) / ".work/delphi" / receipt["artifact_id"]
        return {"room_id": args["room_id"], "artifact_id": receipt["artifact_id"], "receipt_path": receipt["receipt_path"],
                "file_path": receipt["file_path"], "scratch_path": str(scratch), "input_paths": inputs,
                "instructions": worker_delivery(instructions, Path(receipt["file_path"]), scratch),
                "execution_owner": "native_host", "input_templates": _contracts(args["room_id"], mode),
                "next_call": next_call(args, "collect", receipt_paths=[receipt["receipt_path"]])}
    if action == "collect":
        results = []
        for name in args["receipt_paths"]:
            try:
                receipt = json.loads(Path(name).read_text(encoding="utf-8"))
                if receipt.get("room_id") != args["room_id"]:
                    raise ValueError("receipt belongs to another room")
                item = collect_files([name])["deliveries"][0]
                results.append({**item, "file_path": receipt.get("file_path")})
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                results.append({"receipt_path": name, "success": False, "error": str(exc)[:240]})
        return {"ok": all(x.get("success") for x in results), "room_id": args["room_id"], "deliveries": results,
                "next_call": next_call(args, "update", input_path=_contracts(args["room_id"], mode)["update"])}
    if action == "update":
        operations = {"messages": tools.idea_spark_message_post, "links": tools.idea_spark_artifact_link,
                      "needs": tools.idea_spark_need_create, "need_updates": tools.idea_spark_need_update,
                      "artifact_statuses": tools.idea_spark_artifact_status_update, "gates": tools.idea_spark_gate_record}
        check_fields(payload, {"checkpoint", *operations})
        for name in operations:
            if name in payload and (not isinstance(payload[name], list) or any(not isinstance(x, dict) for x in payload[name])):
                raise ValueError(f"{name} must be a list of objects")
            if any(x.get("room_id", args["room_id"]) != args["room_id"] for x in payload.get(name, [])):
                raise ValueError("update cannot address a different room")
        results = []
        for name, handler in operations.items():
            for item in payload.get(name, []):
                results.append({"kind": name, **json.loads(handler({**item, "room_id": args["room_id"]}))})
        if "checkpoint" in payload:
            results.append({"kind": "checkpoint", **save_checkpoint(args["room_id"], payload["checkpoint"])})
        return {"ok": all(x.get("success") for x in results), "room_id": args["room_id"], "updates": results,
                "next_call": next_call(args, "status")}
    if action == "finish":
        if mode == OPEN_DISCUSSION:
            check_fields(payload, {"gate_type", "decision", "rationale", "input_artifact_ids", "score", "status_updates",
                                   "created_by", "decided_by", "metadata"}, {"gate_type", "decision", "rationale"})
            if _room(args["room_id"])["status"] == "gated":
                with IdeaSparkStore().connect() as conn:
                    gate = conn.execute("select * from gates where room_id=? order by rowid desc limit 1",
                                        (args["room_id"],)).fetchone()
                if not gate or any(payload[key] != gate[key] for key in ("gate_type", "decision", "rationale")):
                    raise ValueError("room already finished with a different gate; create a new room")
                result = {"success": True, "gate_id": gate["gate_id"], "room_status": "gated", "idempotent": True}
            else:
                result = _call(tools.idea_spark_gate_record, {**payload, "room_id": args["room_id"], "close_room": True})
        else:
            if payload.get("status") not in {"completed", "stopped"}:
                raise ValueError("finish requires completed or stopped")
            result = save_checkpoint(args["room_id"], payload)
        exported = _call(tools.idea_spark_room_export, {"room_id": args["room_id"]})
        path = _directory(args["room_id"]) / "handoff.md"
        path.write_text(exported["markdown"], encoding="utf-8")
        return {**result, "room_id": args["room_id"], "handoff_path": str(path), "next_call": next_call(args, "status")}
    raise ValueError("unsupported Idea-Spark action")
