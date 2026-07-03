from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    from .config import db_path as default_db_path, runs_dir as default_runs_dir, state_dir as default_state_dir
except ImportError:
    from config import db_path as default_db_path, runs_dir as default_runs_dir, state_dir as default_state_dir

JsonDict = dict[str, Any]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id(prefix: str) -> str:
    return f"pf_{prefix}_{uuid.uuid4().hex[:12]}"


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


class PonderForgeStore:
    """Small durable state layer for Ponder-Forge runs.

    SQLite is the queryable state. JSONL under each run directory is the append-only
    audit trail. This class intentionally does not implement graph or gate logic;
    those belong to later phases.
    """

    def __init__(self, home: Path | str | None = None):
        self.home = Path(home).expanduser().resolve() if home is not None else None
        self.state_dir = default_state_dir(self.home)
        self.runs_dir = default_runs_dir(self.home)
        self.db_path = default_db_path(self.home)

    def initialize(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        migration = Path(__file__).resolve().parent / "migrations" / "0001_init.sql"
        with self.connect(raw=True) as conn:
            conn.executescript(migration.read_text(encoding="utf-8"))
            conn.commit()

    @contextmanager
    def connect(self, raw: bool = False) -> Iterator[sqlite3.Connection]:
        if not raw and not self.db_path.exists():
            self.initialize()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def events_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "events.jsonl"

    def _insert(self, table: str, values: JsonDict) -> JsonDict:
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        sql = f"insert into {table} ({', '.join(columns)}) values ({placeholders})"
        with self.connect() as conn:
            conn.execute(sql, [values[column] for column in columns])
        return values

    def _append_jsonl(self, run_id: str, payload: JsonDict) -> None:
        path = self.events_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json_dumps(payload) + "\n")

    def append_event(
        self,
        run_id: str | None,
        event_type: str,
        payload: JsonDict,
        *,
        task_id: str | None = None,
        session_id: str | None = None,
        actor: str = "system",
    ) -> JsonDict:
        event = {
            "event_id": new_id("event"),
            "run_id": run_id,
            "task_id": task_id,
            "session_id": session_id,
            "event_type": event_type,
            "actor": actor,
            "payload_json": json_dumps(payload),
            "created_at": now_iso(),
        }
        self._insert("events", event)
        if run_id:
            self._append_jsonl(run_id, {**event, "payload": payload})
        return event

    def create_run(
        self,
        goal: str,
        profile: str,
        *,
        budget: JsonDict | None = None,
        config: JsonDict | None = None,
        parent_session_id: str | None = None,
        run_id: str | None = None,
    ) -> JsonDict:
        ts = now_iso()
        row = {
            "run_id": run_id or new_id("run"),
            "parent_session_id": parent_session_id,
            "user_goal": goal,
            "profile": profile,
            "status": "created",
            "budget_json": json_dumps(budget),
            "config_json": json_dumps(config),
            "created_at": ts,
            "updated_at": ts,
            "final_report_md": None,
        }
        self._insert("runs", row)
        self.append_event(row["run_id"], "run_created", {"goal": goal, "profile": profile})
        return row

    def get_run(self, run_id: str) -> JsonDict | None:
        with self.connect() as conn:
            row = conn.execute("select * from runs where run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def create_task(
        self,
        run_id: str,
        role: str,
        goal: str,
        *,
        context: str = "",
        node_id: str | None = None,
        parent_task_id: str | None = None,
        priority: int = 0,
        raw: JsonDict | None = None,
        task_id: str | None = None,
    ) -> JsonDict:
        row = {
            "task_id": task_id or new_id("task"),
            "run_id": run_id,
            "node_id": node_id,
            "parent_task_id": parent_task_id,
            "hermes_child_session_id": None,
            "hermes_subagent_id": None,
            "role": role,
            "goal": goal,
            "context": context,
            "status": "queued",
            "priority": priority,
            "delegation_id": None,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "raw_json": json_dumps(raw),
        }
        self._insert("agent_tasks", row)
        self.append_event(run_id, "task_created", {"role": role, "goal": goal}, task_id=row["task_id"])
        return row

    def create_workflow_node(
        self,
        *,
        run_id: str,
        profile: str,
        node_type: str,
        role: str,
        input_data: JsonDict | None = None,
        node_id: str | None = None,
    ) -> JsonDict:
        ts = now_iso()
        row = {
            "node_id": node_id or new_id("node"),
            "run_id": run_id,
            "profile": profile,
            "node_type": node_type,
            "role": role,
            "status": "queued",
            "input_json": json_dumps(input_data),
            "output_json": "{}",
            "created_at": ts,
            "updated_at": ts,
        }
        self._insert("workflow_nodes", row)
        return row

    def update_run_status(self, run_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute("update runs set status = ?, updated_at = ? where run_id = ?", (status, now_iso(), run_id))

    def update_task_status(self, task_id: str, status: str, error: str | None = None) -> None:
        finished_at = now_iso() if status in {"finished", "failed"} else None
        with self.connect() as conn:
            conn.execute(
                "update agent_tasks set status = ?, error = ?, finished_at = ? where task_id = ?",
                (status, error, finished_at, task_id),
            )

    def update_task_binding(
        self,
        task_id: str,
        *,
        child_session_id: str | None = None,
        subagent_id: str | None = None,
        status: str = "running",
    ) -> None:
        started_at = now_iso() if status == "running" else None
        with self.connect() as conn:
            conn.execute(
                "update agent_tasks set hermes_child_session_id = coalesce(?, hermes_child_session_id), "
                "hermes_subagent_id = coalesce(?, hermes_subagent_id), status = ?, "
                "started_at = coalesce(started_at, ?) where task_id = ?",
                (child_session_id, subagent_id, status, started_at, task_id),
            )

    def get_task(self, task_id: str) -> JsonDict | None:
        with self.connect() as conn:
            row = conn.execute("select * from agent_tasks where task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def get_task_by_session(self, session_id: str) -> JsonDict | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from agent_tasks where hermes_child_session_id = ? order by started_at desc limit 1",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_reports_for_task(self, task_id: str) -> list[JsonDict]:
        with self.connect() as conn:
            rows = conn.execute("select * from reports where task_id = ?", (task_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_report(self, report_id: str) -> JsonDict | None:
        with self.connect() as conn:
            row = conn.execute("select * from reports where report_id = ?", (report_id,)).fetchone()
        return dict(row) if row else None

    def create_report(
        self,
        *,
        run_id: str,
        task_id: str | None,
        role: str,
        title: str | None,
        summary: str,
        confidence: float | None = None,
        raw: JsonDict | None = None,
        report_id: str | None = None,
    ) -> JsonDict:
        row = {
            "report_id": report_id or new_id("report"),
            "run_id": run_id,
            "task_id": task_id,
            "role": role,
            "title": title,
            "summary": summary,
            "confidence": confidence,
            "status": "submitted",
            "created_at": now_iso(),
            "raw_json": json_dumps(raw),
        }
        self._insert("reports", row)
        self.append_event(run_id, "report_created", {"role": role, "title": title}, task_id=task_id)
        return row

    def create_assertion(
        self,
        *,
        run_id: str,
        report_id: str | None,
        profile: str,
        assertion_type: str,
        text: str,
        importance: float = 0.5,
        confidence: float | None = None,
        raw: JsonDict | None = None,
        assertion_id: str | None = None,
    ) -> JsonDict:
        row = {
            "assertion_id": assertion_id or new_id("assertion"),
            "run_id": run_id,
            "report_id": report_id,
            "profile": profile,
            "assertion_type": assertion_type,
            "text": text,
            "importance": importance,
            "confidence": confidence,
            "status": "unverified",
            "subject": None,
            "predicate": None,
            "object": None,
            "supersedes_assertion_id": None,
            "created_at": now_iso(),
            "raw_json": json_dumps(raw),
        }
        self._insert("assertions", row)
        return row

    def create_evidence(
        self,
        *,
        run_id: str,
        report_id: str | None,
        assertion_id: str | None,
        evidence_type: str,
        source_ref: str | None = None,
        title: str | None = None,
        quote_or_observation: str | None = None,
        locator: str | None = None,
        source_date: str | None = None,
        reliability: float = 0.5,
        relevance: float = 0.5,
        directness: float = 0.5,
        freshness: float = 0.5,
        counterevidence: bool = False,
        artifact_path: str | None = None,
        command: str | None = None,
        exit_code: int | None = None,
        metric: JsonDict | None = None,
        raw: JsonDict | None = None,
        evidence_id: str | None = None,
    ) -> JsonDict:
        row = {
            "evidence_id": evidence_id or new_id("evidence"),
            "run_id": run_id,
            "report_id": report_id,
            "assertion_id": assertion_id,
            "evidence_type": evidence_type,
            "source_ref": source_ref,
            "title": title,
            "quote_or_observation": quote_or_observation,
            "locator": locator,
            "source_date": source_date,
            "retrieved_at": now_iso(),
            "reliability": reliability,
            "relevance": relevance,
            "directness": directness,
            "freshness": freshness,
            "counterevidence": 1 if counterevidence else 0,
            "artifact_path": artifact_path,
            "command": command,
            "exit_code": exit_code,
            "metric_json": json_dumps(metric),
            "quote_hash": None,
            "raw_json": json_dumps(raw),
        }
        self._insert("evidence_items", row)
        return row

    def create_artifact(
        self,
        *,
        run_id: str,
        report_id: str | None,
        artifact_type: str,
        path: str | None = None,
        summary: str | None = None,
        raw: JsonDict | None = None,
        artifact_id: str | None = None,
    ) -> JsonDict:
        row = {
            "artifact_id": artifact_id or new_id("artifact"),
            "run_id": run_id,
            "report_id": report_id,
            "artifact_type": artifact_type,
            "path": path,
            "summary": summary,
            "created_at": now_iso(),
            "raw_json": json_dumps(raw),
        }
        self._insert("artifacts", row)
        return row

    def create_edge(
        self,
        *,
        run_id: str,
        src_type: str,
        src_id: str,
        dst_type: str,
        dst_id: str,
        edge_type: str,
        weight: float = 1.0,
        raw: JsonDict | None = None,
        edge_id: str | None = None,
    ) -> JsonDict:
        row = {
            "edge_id": edge_id or new_id("edge"),
            "run_id": run_id,
            "src_type": src_type,
            "src_id": src_id,
            "dst_type": dst_type,
            "dst_id": dst_id,
            "edge_type": edge_type,
            "weight": weight,
            "raw_json": json_dumps(raw),
        }
        self._insert("graph_edges", row)
        return row

    def update_assertion_status(self, assertion_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute("update assertions set status = ? where assertion_id = ?", (status, assertion_id))

    def create_verdict(
        self,
        *,
        run_id: str,
        profile: str,
        target_type: str,
        target_id: str,
        reviewer_role: str,
        reviewer_task_id: str | None,
        verifier_mode: str,
        independent_from_task_id: str | None,
        verdict: str,
        confidence: float | None = None,
        rationale: str | None = None,
        required_actions: list | None = None,
        raw: JsonDict | None = None,
        verdict_id: str | None = None,
    ) -> JsonDict:
        row = {
            "verdict_id": verdict_id or new_id("verdict"),
            "run_id": run_id,
            "profile": profile,
            "target_type": target_type,
            "target_id": target_id,
            "reviewer_role": reviewer_role,
            "reviewer_task_id": reviewer_task_id,
            "verifier_mode": verifier_mode,
            "independent_from_task_id": independent_from_task_id,
            "verdict": verdict,
            "confidence": confidence,
            "rationale": rationale,
            "required_actions_json": json_dumps(required_actions or []),
            "created_at": now_iso(),
            "raw_json": json_dumps(raw),
        }
        self._insert("verification_verdicts", row)
        self.append_event(run_id, "verdict_created", {"target_id": target_id, "verdict": verdict}, task_id=reviewer_task_id)
        return row

    def create_final_statement(
        self,
        run_id: str,
        *,
        section: str,
        text: str,
        status: str = "material",
        raw: JsonDict | None = None,
        statement_id: str | None = None,
    ) -> JsonDict:
        row = {
            "statement_id": statement_id or new_id("statement"),
            "run_id": run_id,
            "section": section,
            "text": text,
            "status": status,
            "created_at": now_iso(),
            "raw_json": json_dumps(raw),
        }
        self._insert("final_statements", row)
        return row

    def link_final_statement(self, statement_id: str, assertion_id: str, *, relation: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "insert or replace into statement_assertion_links "
                "(statement_id, assertion_id, relation) values (?, ?, ?)",
                (statement_id, assertion_id, relation),
            )

    def update_final_report(self, run_id: str, final_report_md: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "update runs set final_report_md = ?, status = ?, updated_at = ? where run_id = ?",
                (final_report_md, "completed", now_iso(), run_id),
            )

    @staticmethod
    def _allowed_tables() -> set[str]:
        return {
            "runs",
            "workflow_nodes",
            "agent_tasks",
            "reports",
            "assertions",
            "evidence_items",
            "artifacts",
            "graph_edges",
            "verification_verdicts",
            "final_statements",
            "statement_assertion_links",
            "events",
        }

    def list_rows(self, table: str, run_id: str | None = None) -> list[JsonDict]:
        if table not in self._allowed_tables():
            raise ValueError(f"unknown table: {table}")
        if run_id is None:
            sql = f"select * from {table}"
            params: tuple[Any, ...] = ()
        else:
            sql = f"select * from {table} where run_id = ?"
            params = (run_id,)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def count_rows(self, table: str) -> int:
        if table not in self._allowed_tables():
            raise ValueError(f"unknown table: {table}")
        with self.connect() as conn:
            row = conn.execute(f"select count(*) as n from {table}").fetchone()
        return int(row["n"])
