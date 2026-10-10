import json
import os
import sqlite3
import time
from importlib import resources
from pathlib import Path
from typing import Callable, TypeVar

try:
    from .config import state_home
except ImportError:
    from config import state_home

T = TypeVar("T")


MIGRATIONS = [("0001_init", "0001_init.sql"), ("0002_file_artifacts", "0002_file_artifacts.sql")]


def default_db_path() -> Path:
    # An explicit Delphi project wins over inherited legacy/global settings.
    override = os.getenv("IDEA_SPARK_DB") if not os.getenv("DELPHI_HOME") else None
    if override:
        return Path(override)
    return state_home() / "idea-spark" / "idea_spark.sqlite3"


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def with_retry(fn: Callable[[], T], attempts: int = 3, delay_s: float = 0.05) -> T:
    last_error = None
    for attempt in range(attempts):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "database is locked" not in str(exc).lower():
                raise
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_s * (attempt + 1))
    raise last_error  # type: ignore[misc]


class IdeaSparkStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else default_db_path()

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def initialize(self) -> None:
        def run() -> None:
            with self.connect() as conn:
                # Rebuilding a referenced table requires FK checks after the copy.
                # Execute every statement in one transaction, including its marker.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                    """
                )
                applied = {
                    row["version"]
                    for row in conn.execute("select version from schema_migrations").fetchall()
                }
                if all(version in applied for version, _ in MIGRATIONS):
                    return
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.execute("BEGIN IMMEDIATE")
                # Another process may have completed initialization while we waited.
                applied = {row["version"] for row in conn.execute("select version from schema_migrations")}
                for version, filename in MIGRATIONS:
                    if version in applied:
                        continue
                    migrations_pkg = f"{__package__}.migrations" if __package__ else None
                    if migrations_pkg:
                        sql = resources.files(migrations_pkg).joinpath(filename).read_text(encoding="utf-8")
                    else:
                        sql = (Path(__file__).resolve().parent / "migrations" / filename).read_text(encoding="utf-8")
                    statement = ""
                    for line in sql.splitlines(keepends=True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            conn.execute(statement)
                            statement = ""
                    if statement.strip():
                        raise ValueError(f"incomplete migration: {filename}")
                    conn.execute(
                        "insert or ignore into schema_migrations(version, applied_at) values (?, datetime('now'))",
                        (version,),
                    )
                if conn.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("migration would leave invalid artifact relationships")

        with_retry(run)
