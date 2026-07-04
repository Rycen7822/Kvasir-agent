import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import quote

try:
    from .export import render_markdown
    from .schemas import ARTIFACT_STATUSES, ARTIFACT_TYPES, GATE_DECISIONS, PROTOCOL, RELATIONS, TOOL_NAMES
    from .store import IdeaSparkStore, canonical_json, content_hash, with_retry
except ImportError:  # source-root script execution
    from export import render_markdown
    from schemas import ARTIFACT_STATUSES, ARTIFACT_TYPES, GATE_DECISIONS, PROTOCOL, RELATIONS, TOOL_NAMES
    from store import IdeaSparkStore, canonical_json, content_hash, with_retry

NEED_STATUSES = {"open", "claimed", "resolved", "stale", "cancelled"}
DEFAULT_DASHBOARD_BASE_URL = "http://127.0.0.1:8765"


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def ok(payload: dict | None = None) -> str:
    return _json({"success": True, **(payload or {})})


def err(message: str, **extra) -> str:
    return _json({"success": False, "error": message, **extra})


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _dashboard_base_url(args: dict) -> str:
    metadata_value = args.get("metadata")
    metadata = metadata_value if isinstance(metadata_value, dict) else {}
    value = args.get("dashboard_base_url") or metadata.get("dashboard_base_url") or DEFAULT_DASHBOARD_BASE_URL
    return str(value).rstrip("/")


def _room_url(room_id: str, args: dict) -> str:
    return f"{_dashboard_base_url(args)}/room/{quote(str(room_id), safe='')}"


def _dashboard_snapshot_url(room_id: str, args: dict) -> str:
    return f"{_dashboard_base_url(args)}/api/rooms/{quote(str(room_id), safe='')}/snapshot"


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _dashboard_check(room_id: str, args: dict) -> dict[str, Any]:
    """Return bounded dashboard reachability details for a newly-created room."""
    timeout_s = float(args.get("dashboard_timeout_s", 1.0))
    room_url = _room_url(room_id, args)
    snapshot_url = _dashboard_snapshot_url(room_id, args)
    try:
        with urllib.request.urlopen(room_url, timeout=timeout_s) as response:
            if response.status != 200:
                raise RuntimeError(f"room page returned HTTP {response.status}")
        with urllib.request.urlopen(snapshot_url, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if response.status != 200 or payload.get("success") is not True:
                raise RuntimeError(f"room snapshot was not successful: {payload}")
    except Exception as exc:
        return {
            "dashboard_checked": True,
            "dashboard_reachable": False,
            "dashboard_snapshot_url": snapshot_url,
            "dashboard_warning": f"dashboard link is not reachable: {type(exc).__name__}: {exc}",
        }
    return {"dashboard_checked": True, "dashboard_reachable": True, "dashboard_snapshot_url": snapshot_url}


def _store() -> IdeaSparkStore:
    store = IdeaSparkStore()
    store.initialize()
    return store


def _loads(value: str, default):
    if not value:
        return default
    return json.loads(value)


def _room(conn: sqlite3.Connection, room_id: str) -> dict | None:
    row = conn.execute("select * from rooms where room_id = ?", (room_id,)).fetchone()
    return dict(row) if row else None


def _require(args: dict, *names: str) -> str | None:
    for name in names:
        if args.get(name) in (None, ""):
            return name
    return None


def _message_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["artifact_ids"] = _loads(item.pop("artifact_ids_json"), [])
    return item


def _expected_agents(room: dict) -> list[str]:
    metadata = _loads(room.get("metadata_json", "{}"), {})
    agents = metadata.get("expected_agents", [])
    return [str(agent) for agent in agents]


def _joined_agents(conn: sqlite3.Connection, room_id: str) -> list[str]:
    rows = conn.execute("select agent_id from participants where room_id = ? order by agent_id", (room_id,)).fetchall()
    return [row["agent_id"] for row in rows]


def _room_counts(conn: sqlite3.Connection, room_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in ["participants", "messages", "artifacts", "gates"]:
        counts[name] = conn.execute(f"select count(*) as n from {name} where room_id = ?", (room_id,)).fetchone()["n"]
    counts["open_needs"] = conn.execute(
        "select count(*) as n from open_needs where room_id = ? and status in ('open', 'claimed')",
        (room_id,),
    ).fetchone()["n"]
    counts["total_needs"] = conn.execute(
        "select count(*) as n from open_needs where room_id = ?",
        (room_id,),
    ).fetchone()["n"]
    return counts


def _gate_dict(row: sqlite3.Row) -> dict[str, Any]:
    gate = dict(row)
    gate["input_artifact_ids"] = _loads(gate.pop("input_artifact_ids_json"), [])
    gate["score"] = _loads(gate.pop("score_json"), {})
    gate["metadata"] = _loads(gate.pop("metadata_json"), {})
    return gate


def _latest_gate(conn: sqlite3.Connection, room_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "select * from gates where room_id = ? order by created_at desc, gate_id desc limit 1",
        (room_id,),
    ).fetchone()
    return _gate_dict(row) if row else None


def _open_need_summary(conn: sqlite3.Connection, room_id: str) -> dict[str, int]:
    summary = {"open": 0, "claimed": 0, "resolved": 0, "stale": 0, "cancelled": 0}
    rows = conn.execute("select status, count(*) as n from open_needs where room_id = ? group by status", (room_id,)).fetchall()
    for row in rows:
        summary[str(row["status"])] = row["n"]
    return summary


def _room_cursors(conn: sqlite3.Connection, room_id: str) -> dict[str, Any]:
    last_message = conn.execute("select max(message_id) as value from messages where room_id = ?", (room_id,)).fetchone()["value"]
    last_artifact = conn.execute("select max(updated_at) as value from artifacts where room_id = ?", (room_id,)).fetchone()["value"]
    last_gate = conn.execute("select max(created_at) as value from gates where room_id = ?", (room_id,)).fetchone()["value"]
    last_need = conn.execute("select max(updated_at) as value from open_needs where room_id = ?", (room_id,)).fetchone()["value"]
    return {
        "last_message_id": last_message,
        "last_artifact_updated_at": last_artifact,
        "last_gate_created_at": last_gate,
        "last_need_updated_at": last_need,
    }


def _phase_filter(args: dict) -> tuple[list[str] | None, str | list[str]] | str:
    if "phases" in args and args.get("phases") is not None:
        if not isinstance(args["phases"], list):
            return err("phases must be a list")
        phases = [str(phase) for phase in args["phases"] if phase not in (None, "")]
        if not phases:
            return err("phases must include at least one phase")
        return phases, phases
    phase = args.get("phase")
    if phase in (None, "", "*"):
        return None, "*"
    return [str(phase)], str(phase)


def _arrived_agents(conn: sqlite3.Connection, room_id: str, round_id: str, phases: list[str] | None) -> list[str]:
    params: list[Any] = [room_id, round_id]
    phase_clause = ""
    if phases is not None:
        placeholders = ", ".join("?" for _ in phases)
        phase_clause = f" and phase in ({placeholders})"
        params.extend(phases)
    rows = conn.execute(
        f"""
        select distinct agent_id from messages
        where room_id = ? and round_id = ?{phase_clause}
        order by agent_id
        """,
        params,
    ).fetchall()
    return [row["agent_id"] for row in rows]


def _ordered_subset(order: list[str], values: list[str]) -> list[str]:
    value_set = set(values)
    ordered = [item for item in order if item in value_set]
    ordered.extend(sorted(value_set - set(order)))
    return ordered


def idea_spark_room_create(args: dict, **kwargs) -> str:
    missing = _require(args, "title", "topic")
    if missing:
        return err(f"missing required field: {missing}")
    room_id = args.get("room_id") or _new_id("room")
    metadata = args.get("metadata") or {}
    now = _now()

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            conn.execute(
                """
                insert into rooms(room_id, title, topic, protocol, status, created_by, created_at, metadata_json)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    room_id,
                    args.get("title"),
                    args.get("topic"),
                    args.get("protocol", PROTOCOL),
                    args.get("status", "open"),
                    args.get("created_by"),
                    now,
                    canonical_json(metadata),
                ),
            )
        response = {
            "room_id": room_id,
            "status": args.get("status", "open"),
            "dashboard_url": f"{_dashboard_base_url(args)}/",
            "room_url": _room_url(room_id, args),
            "dashboard_checked": False,
        }
        if _truthy(args.get("check_dashboard")):
            response.update(_dashboard_check(room_id, args))
        return ok(response)

    try:
        return with_retry(run)
    except sqlite3.IntegrityError:
        return err("room already exists", room_id=room_id)


def idea_spark_room_join(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id", "agent_id")
    if missing:
        return err(f"missing required field: {missing}")
    now = _now()

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            if not _room(conn, args["room_id"]):
                return err("unknown room_id", room_id=args["room_id"])
            conn.execute(
                """
                insert into participants(room_id, agent_id, role, display_name, status, joined_at, last_seen_at, metadata_json)
                values (?, ?, ?, ?, 'joined', ?, ?, ?)
                on conflict(room_id, agent_id) do update set
                    role=excluded.role,
                    display_name=excluded.display_name,
                    status='joined',
                    last_seen_at=excluded.last_seen_at,
                    metadata_json=excluded.metadata_json
                """,
                (
                    args["room_id"],
                    args["agent_id"],
                    args.get("role"),
                    args.get("display_name"),
                    now,
                    now,
                    canonical_json(args.get("metadata") or {}),
                ),
            )
        return ok({"room_id": args["room_id"], "agent_id": args["agent_id"], "status": "joined"})

    return with_retry(run)


def idea_spark_message_post(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id", "agent_id", "content")
    if missing:
        return err(f"missing required field: {missing}")
    artifact_ids = args.get("artifact_ids") or []
    if not isinstance(artifact_ids, list):
        return err("artifact_ids must be a list")

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            if not _room(conn, args["room_id"]):
                return err("unknown room_id", room_id=args["room_id"])
            cur = conn.execute(
                """
                insert into messages(room_id, round_id, phase, agent_id, role, content, artifact_ids_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    args["room_id"],
                    args.get("round_id"),
                    args.get("phase"),
                    args["agent_id"],
                    args.get("role"),
                    args["content"],
                    canonical_json(artifact_ids),
                    _now(),
                ),
            )
        return ok({"room_id": args["room_id"], "message_id": cur.lastrowid})

    return with_retry(run)


def idea_spark_message_read(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id")
    if missing:
        return err(f"missing required field: {missing}")
    order = str(args.get("order", "asc")).lower()
    if order not in {"asc", "desc"}:
        return err("order must be asc or desc", order=args.get("order"))
    limit = min(int(args.get("limit", 100)), 200)
    clauses = ["room_id = ?"]
    params: list[Any] = [args["room_id"]]
    if args.get("after_message_id") is not None:
        clauses.append("message_id > ?")
        params.append(int(args["after_message_id"]))
    for field in ("round_id", "phase", "agent_id"):
        if args.get(field) is not None:
            clauses.append(f"{field} = ?")
            params.append(args[field])
    params.append(limit)

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            if not _room(conn, args["room_id"]):
                return err("unknown room_id", room_id=args["room_id"])
            rows = conn.execute(
                f"select * from messages where {' and '.join(clauses)} order by message_id {order} limit ?",
                params,
            ).fetchall()
        messages = [_message_dict(row) for row in rows]
        last_message_id = max((message["message_id"] for message in messages), default=None)
        return ok({"room_id": args["room_id"], "messages": messages, "next_cursor": {"last_message_id": last_message_id}})

    return with_retry(run)


def idea_spark_room_status(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id")
    if missing:
        return err(f"missing required field: {missing}")

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            room = _room(conn, args["room_id"])
            if not room:
                return err("unknown room_id", room_id=args["room_id"])
            counts = _room_counts(conn, args["room_id"])
            joined = _joined_agents(conn, args["room_id"])
            latest_gate = _latest_gate(conn, args["room_id"])
            open_need_summary = _open_need_summary(conn, args["room_id"])
            cursors = _room_cursors(conn, args["room_id"])
        expected = _expected_agents(room)
        missing_agents = [agent for agent in expected if agent not in set(joined)]
        return ok(
            {
                "room_id": args["room_id"],
                "status": room["status"],
                "counts": counts,
                "expected_agents": expected,
                "joined_agents": joined,
                "missing_expected_agents": missing_agents,
                "latest_gate": latest_gate,
                "has_terminal_gate": room["status"] == "gated",
                "open_need_summary": open_need_summary,
                "cursors": cursors,
            }
        )

    return with_retry(run)


def idea_spark_round_wait(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id", "round_id")
    if missing:
        return err(f"missing required field: {missing}")
    phase_filter = _phase_filter(args)
    if isinstance(phase_filter, str):
        return phase_filter
    phases, phase_filter_value = phase_filter
    expected_override = None
    if "expected_agents" in args:
        if not isinstance(args["expected_agents"], list):
            return err("expected_agents must be a list")
        expected_override = [str(agent) for agent in args["expected_agents"]]
    timeout_s = float(args.get("timeout_s", 120))
    deadline = time.monotonic() + timeout_s
    store = _store()

    def snapshot() -> tuple[str, list[str], list[str]] | str:
        with store.connect() as conn:
            room = _room(conn, args["room_id"])
            if not room:
                return err("unknown room_id", room_id=args["room_id"])
            expected = expected_override if expected_override is not None else _expected_agents(room)
            arrived_raw = _arrived_agents(conn, args["room_id"], args["round_id"], phases)
        arrived = _ordered_subset(expected, arrived_raw)
        missing_agents = [agent for agent in expected if agent not in set(arrived_raw)]
        status = "complete" if not missing_agents else "waiting"
        return status, arrived, missing_agents

    while True:
        state = snapshot()
        if isinstance(state, str):
            return state
        status, arrived, missing_agents = state
        if status == "complete":
            return ok({"status": "complete", "arrived_agents": arrived, "missing_agents": [], "phase_filter": phase_filter_value})
        if time.monotonic() >= deadline:
            return ok(
                {
                    "status": "timeout",
                    "arrived_agents": arrived,
                    "missing_agents": missing_agents,
                    "phase_filter": phase_filter_value,
                    "instruction": "continue with partial state and record missing agents explicitly",
                }
            )
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def _all_messages(conn: sqlite3.Connection, room_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("select * from messages where room_id = ? order by message_id", (room_id,)).fetchall()
    return [_message_dict(row) for row in rows]


def _all_artifacts(conn: sqlite3.Connection, room_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("select * from artifacts where room_id = ? order by created_at, artifact_id", (room_id,)).fetchall()
    return [_artifact_dict(conn, row, 0) for row in rows]


def _all_gates(conn: sqlite3.Connection, room_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("select * from gates where room_id = ? order by created_at, gate_id", (room_id,)).fetchall()
    return [_gate_dict(row) for row in rows]


def _all_open_needs(conn: sqlite3.Connection, room_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("select * from open_needs where room_id = ? order by pressure_score desc, created_at", (room_id,)).fetchall()
    return [_need_dict(row) for row in rows]


def _need_dict(row: sqlite3.Row) -> dict[str, Any]:
    need = dict(row)
    need["metadata"] = _loads(need.pop("metadata_json"), {})
    return need


def idea_spark_room_export(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id")
    if missing:
        return err(f"missing required field: {missing}")
    if args.get("format", "markdown") != "markdown":
        return err("unsupported export format", format=args.get("format"))

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            room = _room(conn, args["room_id"])
            if not room:
                return err("unknown room_id", room_id=args["room_id"])
            messages = _all_messages(conn, args["room_id"])
            artifacts = _all_artifacts(conn, args["room_id"])
            gates = _all_gates(conn, args["room_id"])
            open_needs = _all_open_needs(conn, args["room_id"])
            artifact_count = len(artifacts)
            gate_count = len(gates)
            open_need_count = len(open_needs)
        return ok(
            {
                "room_id": args["room_id"],
                "format": "markdown",
                "markdown": render_markdown(room, messages, artifacts, gates, open_needs),
                "artifact_count": artifact_count,
                "gate_count": gate_count,
                "open_need_count": open_need_count,
            }
        )

    return with_retry(run)


def _artifact(conn: sqlite3.Connection, artifact_id: str) -> dict | None:
    row = conn.execute("select * from artifacts where artifact_id = ?", (artifact_id,)).fetchone()
    return dict(row) if row else None


def _artifact_in_room(conn: sqlite3.Connection, room_id: str, artifact_id: str) -> dict | None:
    artifact = _artifact(conn, artifact_id)
    if not artifact or artifact["room_id"] != room_id:
        return None
    return artifact


def _validate_artifact_refs(conn: sqlite3.Connection, room_id: str, artifact_ids: list[str]) -> str | None:
    for artifact_id in artifact_ids:
        if not _artifact_in_room(conn, room_id, artifact_id):
            return artifact_id
    return None


def _link_dict(row: sqlite3.Row) -> dict:
    return {
        "source_artifact_id": row["source_artifact_id"],
        "relation": row["relation"],
        "target_artifact_id": row["target_artifact_id"],
    }


def _artifact_dict(conn: sqlite3.Connection, row: sqlite3.Row, relation_depth: int) -> dict:
    item = dict(row)
    item["content"] = _loads(item.pop("content_json"), {})
    item["metadata"] = _loads(item.pop("metadata_json"), {})
    if relation_depth >= 1:
        inbound = conn.execute(
            """
            select source_artifact_id, relation, target_artifact_id from artifact_links
            where room_id = ? and target_artifact_id = ? order by link_id
            """,
            (item["room_id"], item["artifact_id"]),
        ).fetchall()
        outbound = conn.execute(
            """
            select source_artifact_id, relation, target_artifact_id from artifact_links
            where room_id = ? and source_artifact_id = ? order by link_id
            """,
            (item["room_id"], item["artifact_id"]),
        ).fetchall()
        item["inbound_links"] = [_link_dict(row) for row in inbound]
        item["outbound_links"] = [_link_dict(row) for row in outbound]
    return item


def _insert_artifact(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    artifact_type: str,
    producer_agent: str,
    title: str | None,
    content: dict,
    status: str = "proposed",
    metadata: dict | None = None,
    artifact_id: str | None = None,
) -> tuple[str, str, bool]:
    digest = content_hash(content)
    now = _now()
    artifact_id = artifact_id or _new_id("artifact")
    try:
        conn.execute(
            """
            insert into artifacts(
                artifact_id, room_id, schema_id, artifact_type, producer_agent, title,
                content_json, content_hash, status, confidence, created_at, updated_at, metadata_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                room_id,
                PROTOCOL,
                artifact_type,
                producer_agent,
                title,
                canonical_json(content),
                digest,
                status,
                None,
                now,
                now,
                canonical_json(metadata or {}),
            ),
        )
        return artifact_id, digest, False
    except sqlite3.IntegrityError:
        row = conn.execute(
            "select artifact_id from artifacts where room_id = ? and artifact_type = ? and content_hash = ?",
            (room_id, artifact_type, digest),
        ).fetchone()
        if not row:
            raise
        return row["artifact_id"], digest, True


def _insert_link(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    source_artifact_id: str,
    relation: str,
    target_artifact_id: str,
    created_by: str | None = None,
) -> int | None:
    conn.execute(
        """
        insert or ignore into artifact_links(room_id, source_artifact_id, relation, target_artifact_id, created_by, created_at)
        values (?, ?, ?, ?, ?, ?)
        """,
        (room_id, source_artifact_id, relation, target_artifact_id, created_by, _now()),
    )
    row = conn.execute(
        """
        select link_id from artifact_links
        where room_id = ? and source_artifact_id = ? and relation = ? and target_artifact_id = ?
        """,
        (room_id, source_artifact_id, relation, target_artifact_id),
    ).fetchone()
    return row["link_id"] if row else None


def idea_spark_artifact_create(args: dict, **kwargs) -> str:
    args = dict(args)
    if "artifact_type" not in args and "type" in args:
        args["artifact_type"] = args["type"]
    if "producer_agent" not in args:
        if "created_by" in args:
            args["producer_agent"] = args["created_by"]
        elif "agent_id" in args:
            args["producer_agent"] = args["agent_id"]
    if "content" in args and not isinstance(args["content"], dict):
        args["content"] = {"text": str(args["content"])}
    status = args.get("status", "proposed")
    missing = _require(args, "room_id", "artifact_type", "producer_agent", "content")
    if missing:
        return err(f"missing required field: {missing}")
    if args["artifact_type"] not in ARTIFACT_TYPES:
        return err("invalid artifact_type", artifact_type=args["artifact_type"])
    if status not in ARTIFACT_STATUSES:
        return err("invalid artifact status", status=status)
    if not isinstance(args["content"], dict):
        return err("content must be an object")
    parent_links = args.get("parent_links") or []
    if not isinstance(parent_links, list):
        return err("parent_links must be a list")
    for link in parent_links:
        if link.get("relation") not in RELATIONS:
            return err("invalid relation", relation=link.get("relation"))
        if not link.get("source_artifact_id"):
            return err("parent link missing source_artifact_id")

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            if not _room(conn, args["room_id"]):
                return err("unknown room_id", room_id=args["room_id"])
            for link in parent_links:
                if not _artifact_in_room(conn, args["room_id"], link["source_artifact_id"]):
                    return err("unknown parent artifact", artifact_id=link["source_artifact_id"])
            artifact_id, digest, deduplicated = _insert_artifact(
                conn,
                room_id=args["room_id"],
                artifact_type=args["artifact_type"],
                producer_agent=args["producer_agent"],
                title=args.get("title"),
                content=args["content"],
                status=status,
                metadata=args.get("metadata") or {},
            )
            if not deduplicated:
                for link in parent_links:
                    _insert_link(
                        conn,
                        room_id=args["room_id"],
                        source_artifact_id=link["source_artifact_id"],
                        relation=link["relation"],
                        target_artifact_id=artifact_id,
                        created_by=args["producer_agent"],
                    )
        return ok({"artifact_id": artifact_id, "content_hash": digest, "status": status, "deduplicated": deduplicated})

    return with_retry(run)


def idea_spark_artifact_read(args: dict, **kwargs) -> str:
    args = dict(args)
    if "artifact_ids" not in args and "artifact_id" in args:
        args["artifact_ids"] = [args["artifact_id"]]
    if "artifact_type" not in args and "type" in args:
        args["artifact_type"] = args["type"]
    if "producer_agent" not in args and "created_by" in args:
        args["producer_agent"] = args["created_by"]
    missing = _require(args, "room_id")
    if missing:
        return err(f"missing required field: {missing}")
    order = str(args.get("order", "asc")).lower()
    if order not in {"asc", "desc"}:
        return err("order must be asc or desc", order=args.get("order"))
    limit = min(int(args.get("limit", 200)), 200)
    relation_depth = int(args.get("relation_depth", 0))
    clauses = ["room_id = ?"]
    params: list[Any] = [args["room_id"]]
    artifact_ids = args.get("artifact_ids") or []
    if artifact_ids:
        placeholders = ",".join("?" for _ in artifact_ids)
        clauses.append(f"artifact_id in ({placeholders})")
        params.extend(artifact_ids)
    if args.get("created_after") is not None:
        clauses.append("created_at > ?")
        params.append(args["created_after"])
    if args.get("updated_after") is not None:
        clauses.append("updated_at > ?")
        params.append(args["updated_after"])
    sort_column = "updated_at" if args.get("updated_after") is not None else "created_at"
    for arg_name, column in [("artifact_type", "artifact_type"), ("status", "status"), ("producer_agent", "producer_agent")]:
        if args.get(arg_name):
            clauses.append(f"{column} = ?")
            params.append(args[arg_name])
    params.append(limit)

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            if not _room(conn, args["room_id"]):
                return err("unknown room_id", room_id=args["room_id"])
            rows = conn.execute(
                f"select * from artifacts where {' and '.join(clauses)} order by {sort_column} {order}, artifact_id {order} limit ?",
                params,
            ).fetchall()
            artifacts = [_artifact_dict(conn, row, relation_depth) for row in rows]
        last_updated_at = max((artifact["updated_at"] for artifact in artifacts), default=None)
        return ok(
            {
                "room_id": args["room_id"],
                "artifacts": artifacts,
                "next_cursor": {"last_artifact_updated_at": last_updated_at},
            }
        )

    return with_retry(run)


def idea_spark_artifact_link(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id", "source_artifact_id", "relation", "target_artifact_id")
    if missing:
        return err(f"missing required field: {missing}")
    if args["relation"] not in RELATIONS:
        return err("invalid relation", relation=args["relation"])

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            if not _room(conn, args["room_id"]):
                return err("unknown room_id", room_id=args["room_id"])
            if not _artifact_in_room(conn, args["room_id"], args["source_artifact_id"]):
                return err("unknown source_artifact_id", artifact_id=args["source_artifact_id"])
            if not _artifact_in_room(conn, args["room_id"], args["target_artifact_id"]):
                return err("unknown target_artifact_id", artifact_id=args["target_artifact_id"])
            link_id = _insert_link(
                conn,
                room_id=args["room_id"],
                source_artifact_id=args["source_artifact_id"],
                relation=args["relation"],
                target_artifact_id=args["target_artifact_id"],
                created_by=args.get("created_by"),
            )
        return ok({"room_id": args["room_id"], "link_id": link_id})

    return with_retry(run)


def idea_spark_artifact_status_update(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id", "artifact_id", "status")
    if missing:
        return err(f"missing required field: {missing}")
    if args["status"] not in ARTIFACT_STATUSES:
        return err("invalid artifact status", status=args["status"])

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            if not _artifact_in_room(conn, args["room_id"], args["artifact_id"]):
                return err("unknown artifact_id", artifact_id=args["artifact_id"])
            conn.execute(
                "update artifacts set status = ?, updated_at = ? where artifact_id = ?",
                (args["status"], _now(), args["artifact_id"]),
            )
        return ok({"artifact_id": args["artifact_id"], "status": args["status"]})

    return with_retry(run)


def _gate_link_relation(decision: str) -> str:
    return "passes_gate" if decision == "accepted" else "rejected_by_gate"


def idea_spark_gate_record(args: dict, **kwargs) -> str:
    args = dict(args)
    if "created_by" not in args and "decided_by" in args:
        args["created_by"] = args["decided_by"]
    missing = _require(args, "room_id", "gate_type", "decision", "rationale")
    if missing:
        return err(f"missing required field: {missing}")
    if args["decision"] not in GATE_DECISIONS:
        return err("invalid gate decision", decision=args["decision"])
    input_artifact_ids = args.get("input_artifact_ids") or []
    status_updates = args.get("status_updates") or []
    for update in status_updates:
        if update.get("status") not in ARTIFACT_STATUSES:
            return err("invalid artifact status", status=update.get("status"))
        if not update.get("artifact_id"):
            return err("status update missing artifact_id")

    def run() -> str:
        gate_id = _new_id("gate")
        gate_artifact_id = _new_id("artifact")
        gate_content = {
            "gate_id": gate_id,
            "gate_type": args["gate_type"],
            "input_artifact_ids": input_artifact_ids,
            "decision": args["decision"],
            "score": args.get("score") or {},
            "rationale": args["rationale"],
            "metadata": args.get("metadata") or {},
        }
        room_status = "gated" if args.get("close_room") else None
        store = _store()
        with store.connect() as conn:
            room = _room(conn, args["room_id"])
            if not room:
                return err("unknown room_id", room_id=args["room_id"])
            if room_status is None:
                room_status = room["status"]
            bad_ref = _validate_artifact_refs(conn, args["room_id"], input_artifact_ids)
            if bad_ref:
                return err("unknown input artifact", artifact_id=bad_ref)
            bad_update = _validate_artifact_refs(conn, args["room_id"], [u["artifact_id"] for u in status_updates])
            if bad_update:
                return err("unknown status update artifact", artifact_id=bad_update)
            conn.execute(
                """
                insert into gates(gate_id, room_id, gate_type, input_artifact_ids_json, decision, score_json, rationale, created_by, created_at, metadata_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gate_id,
                    args["room_id"],
                    args["gate_type"],
                    canonical_json(input_artifact_ids),
                    args["decision"],
                    canonical_json(args.get("score") or {}),
                    args["rationale"],
                    args.get("created_by"),
                    _now(),
                    canonical_json(args.get("metadata") or {}),
                ),
            )
            _insert_artifact(
                conn,
                room_id=args["room_id"],
                artifact_type="GateDecision",
                producer_agent=args.get("created_by") or "gatekeeper",
                title=f"{args['gate_type']} gate: {args['decision']}",
                content=gate_content,
                status="accepted",
                metadata={"gate_id": gate_id},
                artifact_id=gate_artifact_id,
            )
            if args.get("close_room"):
                conn.execute("update rooms set status = ? where room_id = ?", ("gated", args["room_id"]))
            for update in status_updates:
                conn.execute(
                    "update artifacts set status = ?, updated_at = ? where artifact_id = ?",
                    (update["status"], _now(), update["artifact_id"]),
                )
                _insert_link(
                    conn,
                    room_id=args["room_id"],
                    source_artifact_id=gate_artifact_id,
                    relation=_gate_link_relation(args["decision"]),
                    target_artifact_id=update["artifact_id"],
                    created_by=args.get("created_by"),
                )
        return ok(
            {
                "gate_id": gate_id,
                "gate_artifact_id": gate_artifact_id,
                "decision": args["decision"],
                "room_status": room_status,
            }
        )

    return with_retry(run)


def idea_spark_need_create(args: dict, **kwargs) -> str:
    args = dict(args)
    if "pressure_score" not in args:
        args["pressure_score"] = 0.5
    missing = _require(args, "room_id", "target_artifact_type", "query", "rationale")
    if missing:
        return err(f"missing required field: {missing}")
    if args["target_artifact_type"] not in ARTIFACT_TYPES:
        return err("invalid target_artifact_type", target_artifact_type=args["target_artifact_type"])
    pressure_score = float(args["pressure_score"])
    if pressure_score < 0.0 or pressure_score > 1.0:
        return err("pressure_score out of range", pressure_score=pressure_score)

    def run() -> str:
        need_id = _new_id("need")
        now = _now()
        store = _store()
        with store.connect() as conn:
            if not _room(conn, args["room_id"]):
                return err("unknown room_id", room_id=args["room_id"])
            conn.execute(
                """
                insert into open_needs(
                    need_id, room_id, target_artifact_type, query, rationale, pressure_score,
                    status, claimed_by_agent, created_by, created_at, updated_at, metadata_json
                ) values (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (
                    need_id,
                    args["room_id"],
                    args["target_artifact_type"],
                    args["query"],
                    args["rationale"],
                    pressure_score,
                    args.get("claimed_by_agent"),
                    args.get("created_by"),
                    now,
                    now,
                    canonical_json(args.get("metadata") or {}),
                ),
            )
        return ok({"need_id": need_id, "status": "open", "pressure_score": pressure_score})

    return with_retry(run)


def idea_spark_need_update(args: dict, **kwargs) -> str:
    missing = _require(args, "room_id", "need_id", "status", "updated_by")
    if missing:
        return err(f"missing required field: {missing}")
    if args["status"] not in NEED_STATUSES:
        return err("invalid need status", status=args["status"])
    resolution_artifact_ids = args.get("resolution_artifact_ids") or []
    if not isinstance(resolution_artifact_ids, list):
        return err("resolution_artifact_ids must be a list")

    def run() -> str:
        store = _store()
        with store.connect() as conn:
            if not _room(conn, args["room_id"]):
                return err("unknown room_id", room_id=args["room_id"])
            row = conn.execute(
                "select * from open_needs where room_id = ? and need_id = ?",
                (args["room_id"], args["need_id"]),
            ).fetchone()
            if not row:
                return err("unknown need_id", need_id=args["need_id"])
            bad_ref = _validate_artifact_refs(conn, args["room_id"], resolution_artifact_ids)
            if bad_ref:
                return err("unknown resolution artifact", artifact_id=bad_ref)
            current = _need_dict(row)
            metadata = {**current["metadata"], **(args.get("metadata") or {})}
            if resolution_artifact_ids:
                metadata["resolution_artifact_ids"] = resolution_artifact_ids
            if "resolution_rationale" in args:
                metadata["resolution_rationale"] = args["resolution_rationale"]
            metadata["updated_by"] = args["updated_by"]
            if args["status"] == "claimed":
                claimed_by_agent = args.get("claimed_by_agent") or args["updated_by"]
            elif args["status"] == "open" and "claimed_by_agent" not in args:
                claimed_by_agent = None
            else:
                claimed_by_agent = args.get("claimed_by_agent", current.get("claimed_by_agent"))
            conn.execute(
                """
                update open_needs
                set status = ?, claimed_by_agent = ?, updated_at = ?, metadata_json = ?
                where room_id = ? and need_id = ?
                """,
                (
                    args["status"],
                    claimed_by_agent,
                    _now(),
                    canonical_json(metadata),
                    args["room_id"],
                    args["need_id"],
                ),
            )
        return ok({"room_id": args["room_id"], "need_id": args["need_id"], "status": args["status"]})

    return with_retry(run)


_TOOL_DESCRIPTIONS = {
    "idea_spark_room_create": "Create an Idea-Spark shared-ledger review room and return room_url for the dashboard. Pass check_dashboard=true to perform a bounded dashboard reachability check before presenting the link as openable. Set metadata.expected_agents when round barriers should wait for named child agents. For protocol guidance, load skill idea-spark:idea-spark-usage.",
    "idea_spark_room_join": "Register a delegate_task child agent in an Idea-Spark room. Children should call this first before reading or writing room state.",
    "idea_spark_room_status": "Return room status, ledger counts, and expected agents that have not joined yet.",
    "idea_spark_message_post": "Post a concise round/phase narrative update, optionally linked to artifact IDs. Use artifacts for durable claims rather than only free text.",
    "idea_spark_message_read": "Read room messages, optionally filtered by round_id, phase, or agent_id.",
    "idea_spark_round_wait": "Wait for expected agents to post in a round. Optional phase filters exact phase, phase='*' or omitted matches any phase, and phases=[...] matches several role-specific phases. Always use a finite timeout_s and continue with partial state on timeout.",
    "idea_spark_artifact_create": "Create a typed durable review artifact such as ResearchGoal, IdeaCard, AtomicClaim, NoveltyObjection, ExperimentPlan, ScoreCard, GateDecision, or OpenNeed.",
    "idea_spark_artifact_read": "Read artifacts in a room, optionally by artifact_id, type, or status, including linked provenance.",
    "idea_spark_artifact_link": "Link two artifacts with a typed provenance relation such as supports, critiques, rebuts, supersedes, requires, or cites.",
    "idea_spark_artifact_status_update": "Update an artifact lifecycle status: proposed, accepted, rejected, superseded, retracted, or stale.",
    "idea_spark_gate_record": "Record an explicit gate decision over input artifacts. Final conclusions require this tool, not chat consensus alone.",
    "idea_spark_need_create": "Create an open evidence/review need when information is missing or unresolved risk remains.",
    "idea_spark_need_update": "Update an OpenNeed lifecycle status and attach resolution artifacts or claim metadata.",
    "idea_spark_room_export": "Export the deterministic Markdown report for an Idea-Spark room from ledger state.",
}

_TOOL_PROPERTIES = {
    "room_id": {"type": "string", "description": "Idea-Spark room id."},
    "agent_id": {"type": "string", "description": "Stable child/parent agent id."},
    "role": {"type": "string", "description": "Role name, e.g. PriorArtBreaker or Gatekeeper."},
    "round_id": {"type": "string", "description": "Round identifier such as r1."},
    "phase": {"type": "string", "description": "Optional protocol phase such as review, rebuttal, gate, or '*' for any phase in round_wait."},
    "artifact_id": {"type": "string", "description": "Artifact id."},
    "need_id": {"type": "string", "description": "OpenNeed id."},
    "artifact_ids": {"type": "array", "items": {"type": "string"}, "description": "Artifact ids linked to this message."},
    "expected_agents": {"type": "array", "items": {"type": "string"}, "description": "Expected agent ids for this barrier."},
    "phases": {"type": "array", "items": {"type": "string"}, "description": "Optional phase list for a multi-phase round_wait barrier."},
    "metadata": {"type": "object", "description": "Optional structured metadata.", "additionalProperties": True},
}

_SCHEMA_FIELDS = {
    "idea_spark_room_create": ["room_id", "title", "topic", "created_by", "protocol", "status", "dashboard_base_url", "check_dashboard", "dashboard_timeout_s", "metadata"],
    "idea_spark_room_join": ["room_id", "agent_id", "role", "display_name", "metadata"],
    "idea_spark_room_status": ["room_id"],
    "idea_spark_message_post": ["room_id", "round_id", "phase", "agent_id", "role", "content", "artifact_ids"],
    "idea_spark_message_read": ["room_id", "round_id", "phase", "agent_id", "after_message_id", "order", "limit"],
    "idea_spark_round_wait": ["room_id", "round_id", "phase", "phases", "expected_agents", "timeout_s"],
    "idea_spark_artifact_create": ["room_id", "type", "title", "content", "created_by", "status", "metadata"],
    "idea_spark_artifact_read": ["room_id", "artifact_id", "type", "status", "created_after", "updated_after", "order", "limit"],
    "idea_spark_artifact_link": ["room_id", "source_artifact_id", "target_artifact_id", "relation", "created_by", "metadata"],
    "idea_spark_artifact_status_update": ["room_id", "artifact_id", "status", "updated_by", "rationale"],
    "idea_spark_gate_record": ["room_id", "gate_type", "decision", "input_artifact_ids", "rationale", "decided_by", "score", "metadata", "close_room"],
    "idea_spark_need_create": ["room_id", "target_artifact_type", "query", "rationale", "pressure_score", "claimed_by_agent", "created_by", "metadata"],
    "idea_spark_need_update": [
        "room_id",
        "need_id",
        "status",
        "claimed_by_agent",
        "resolution_artifact_ids",
        "resolution_rationale",
        "updated_by",
        "metadata",
    ],
    "idea_spark_room_export": ["room_id", "format"],
}

_REQUIRED_FIELDS = {
    "idea_spark_room_create": ["title", "topic"],
    "idea_spark_room_join": ["room_id", "agent_id"],
    "idea_spark_room_status": ["room_id"],
    "idea_spark_message_post": ["room_id", "agent_id", "content"],
    "idea_spark_message_read": ["room_id"],
    "idea_spark_round_wait": ["room_id", "round_id"],
    "idea_spark_artifact_create": ["room_id", "type", "title", "content", "created_by"],
    "idea_spark_artifact_read": ["room_id"],
    "idea_spark_artifact_link": ["room_id", "source_artifact_id", "target_artifact_id", "relation", "created_by"],
    "idea_spark_artifact_status_update": ["room_id", "artifact_id", "status", "updated_by"],
    "idea_spark_gate_record": ["room_id", "gate_type", "decision", "input_artifact_ids", "rationale", "decided_by"],
    "idea_spark_need_create": ["room_id", "target_artifact_type", "query", "rationale"],
    "idea_spark_need_update": ["room_id", "need_id", "status", "updated_by"],
    "idea_spark_room_export": ["room_id"],
}

_FIELD_OVERRIDES = {
    "title": {"type": "string"},
    "topic": {"type": "string"},
    "created_by": {"type": "string"},
    "protocol": {"type": "string"},
    "status": {"type": "string"},
    "dashboard_base_url": {"type": "string", "description": "Optional dashboard base URL used to compute room_url, e.g. http://127.0.0.1:8879."},
    "check_dashboard": {"type": "boolean"},
    "dashboard_timeout_s": {"type": "number", "minimum": 0},
    "display_name": {"type": "string"},
    "content": {"type": "string"},
    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
    "after_message_id": {"type": "integer", "minimum": 0},
    "created_after": {"type": "string"},
    "updated_after": {"type": "string"},
    "order": {"type": "string", "enum": ["asc", "desc"]},
    "timeout_s": {"type": "number", "minimum": 0},
    "type": {"type": "string", "enum": sorted(ARTIFACT_TYPES)},
    "source_artifact_id": {"type": "string"},
    "target_artifact_id": {"type": "string"},
    "relation": {"type": "string", "enum": sorted(RELATIONS)},
    "updated_by": {"type": "string"},
    "rationale": {"type": "string"},
    "gate_type": {"type": "string"},
    "decision": {"type": "string", "enum": sorted(GATE_DECISIONS)},
    "input_artifact_ids": {"type": "array", "items": {"type": "string"}},
    "resolution_artifact_ids": {"type": "array", "items": {"type": "string"}},
    "resolution_rationale": {"type": "string"},
    "decided_by": {"type": "string"},
    "score": {"type": "object", "additionalProperties": True},
    "close_room": {"type": "boolean"},
    "target_artifact_type": {"type": "string", "enum": sorted(ARTIFACT_TYPES)},
    "query": {"type": "string"},
    "pressure_score": {"type": "number"},
    "claimed_by_agent": {"type": "string"},
    "format": {"type": "string", "enum": ["markdown"]},
}


def _property_schema(field: str) -> dict:
    return dict(_TOOL_PROPERTIES.get(field, _FIELD_OVERRIDES.get(field, {"type": "string"})))


def schema_for(name: str) -> dict:
    fields = _SCHEMA_FIELDS.get(name, [])
    return {
        "name": name,
        "description": _TOOL_DESCRIPTIONS.get(name, f"Idea-Spark tool: {name}"),
        "parameters": {
            "type": "object",
            "properties": {field: _property_schema(field) for field in fields},
            "required": _REQUIRED_FIELDS.get(name, []),
            "additionalProperties": True,
        },
    }


HANDLERS: dict[str, Callable] = {name: globals()[name] for name in TOOL_NAMES}
