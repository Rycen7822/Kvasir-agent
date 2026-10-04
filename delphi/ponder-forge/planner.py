"""A coordinator-authored research board, independent of worker completion."""
from __future__ import annotations
import json

try:
    from .store import PonderForgeStore
    from .strategy import coordinator_prompt, team_effort
except ImportError:
    from store import PonderForgeStore
    from strategy import coordinator_prompt, team_effort

RESOLUTIONS = {"open", "in_progress", "resolved", "cancelled"}


def require_active_run(store: PonderForgeStore, run_id: str) -> dict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    if run["status"] in {"completed", "partial"}:
        raise ValueError("run is closed; start a new run for follow-up work")
    return run


def task_board(store: PonderForgeStore, run_id: str) -> list[dict]:
    result = []
    for row in store.list_rows("workflow_nodes", run_id):
        if row["node_type"] != "research_task":
            continue
        data = json.loads(row["input_json"])
        result.append({"id": row["node_id"], "description": data["description"],
                       "owners": data.get("owners", []), "resolution": row["status"],
                       "notes": data.get("notes", "")})
    return result


def _owners(value) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError("owners must be agent names")
    return list(dict.fromkeys(x.strip() for x in value))


def plan_run(store: PonderForgeStore, run_id: str, payload: dict | None = None) -> dict:
    run = require_active_run(store, run_id)
    if payload is not None:
        items = payload.get("tasks")
        if not isinstance(items, list):
            raise ValueError("board tasks must be a list")
        board = task_board(store, run_id)
        by_id = {x["id"]: x for x in board}
        by_description = {x["description"]: x for x in board}
        changes = []
        # Validate against a working board, including earlier updates in this batch.
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("each board task must be an object")
            row = by_id.get(item.get("id"))
            if item.get("id") and row is None:
                raise ValueError("board task id does not belong to this run")
            description = item.get("description", row["description"] if row else None)
            if not isinstance(description, str) or not description.strip():
                raise ValueError("board task requires a description")
            description = description.strip()
            duplicate = by_description.get(description)
            if row is not None and duplicate is not None and row is not duplicate:
                raise ValueError("description already belongs to another board task")
            row = row or duplicate or {"id": None, "description": description, "owners": [],
                                       "resolution": "open", "notes": ""}
            resolution = item.get("resolution", row["resolution"])
            if resolution not in RESOLUTIONS:
                raise ValueError("resolution must be open, in_progress, resolved or cancelled")
            owners = _owners(item.get("owners", []))
            replace = item.get("replace_owners", False)
            if not isinstance(replace, bool):
                raise ValueError("replace_owners must be a boolean")
            if not replace:
                owners = list(dict.fromkeys(row["owners"] + owners))
            notes = item.get("notes", row["notes"])
            if not isinstance(notes, str):
                raise ValueError("board notes must be text")
            by_description.pop(row["description"], None)
            row.update(description=description, owners=owners, resolution=resolution, notes=notes)
            by_description[description] = row
            if not any(x is row for x in changes):
                changes.append(row)
        for change in changes:
            data = {key: change[key] for key in ("description", "owners", "notes")}
            if change["id"]:
                store.update_workflow_node(run_id, change["id"], change["resolution"], data)
            else:
                store.create_workflow_node(run_id=run_id, profile=run["profile"],
                    node_type="research_task", role="subquestion", input_data=data,
                    status=change["resolution"])
        if changes:
            store.update_run_status(run_id, "researching")
    result = {"run_id": run_id, "profile": run["profile"], "team_effort": team_effort(run),
              "task_board": task_board(store, run_id),
              "tasks": [{key: row[key] for key in ("task_id", "role", "status")}
                        for row in store.list_rows("agent_tasks", run_id)]}
    if payload is None:
        result["coordinator_prompt"] = coordinator_prompt(run)
    return result
