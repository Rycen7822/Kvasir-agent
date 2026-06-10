import hashlib
import json
import os
import sqlite3
import time
from importlib import resources
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


MIGRATIONS = [("0001_init", "0001_init.sql")]


def default_db_path() -> Path:
    override = os.getenv("IDEA_SPARK_DB")
    if override:
        return Path(override)
    hermes_home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    return hermes_home / "idea-spark" / "idea_spark.sqlite3"


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


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
                for version, filename in MIGRATIONS:
                    if version in applied:
                        continue
                    sql = resources.files("idea_spark.migrations").joinpath(filename).read_text(encoding="utf-8")
                    conn.executescript(sql)
                    conn.execute(
                        "insert or ignore into schema_migrations(version, applied_at) values (?, datetime('now'))",
                        (version,),
                    )

        with_retry(run)
