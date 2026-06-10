import os

import pytest


@pytest.fixture
def temp_idea_spark_db(tmp_path, monkeypatch):
    db_path = tmp_path / "idea_spark.sqlite3"
    monkeypatch.setenv("IDEA_SPARK_DB", str(db_path))
    return db_path
