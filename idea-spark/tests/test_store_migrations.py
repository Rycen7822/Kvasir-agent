import sqlite3


EXPECTED_TABLES = {
    "rooms",
    "participants",
    "messages",
    "artifacts",
    "artifact_links",
    "gates",
    "open_needs",
    "schema_migrations",
}


def _tables(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
        ).fetchall()
    return {row[0] for row in rows}


def test_store_creates_mvp_tables_in_temp_db(temp_idea_spark_db):
    from idea_spark.store import IdeaSparkStore

    store = IdeaSparkStore(temp_idea_spark_db)
    store.initialize()

    assert _tables(temp_idea_spark_db) == EXPECTED_TABLES


def test_migrations_are_idempotent(temp_idea_spark_db):
    from idea_spark.store import IdeaSparkStore

    IdeaSparkStore(temp_idea_spark_db).initialize()
    IdeaSparkStore(temp_idea_spark_db).initialize()

    with sqlite3.connect(temp_idea_spark_db) as conn:
        rows = conn.execute("select version from schema_migrations order by version").fetchall()

    assert rows == [("0001_init",)]


def test_content_hash_is_canonical_and_deterministic():
    from idea_spark.store import canonical_json, content_hash

    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}

    assert canonical_json(left) == '{"a":1,"b":2}'
    assert content_hash(left) == content_hash(right)
    assert content_hash(left).startswith("sha256:")


def test_default_db_path_uses_env_override(temp_idea_spark_db):
    from idea_spark.store import default_db_path

    assert default_db_path() == temp_idea_spark_db
