import importlib.util
import os
import sys
from pathlib import Path

import pytest


def _load_flat_source_package() -> None:
    root = Path(__file__).resolve().parents[1]
    init_path = root / "__init__.py"
    module = sys.modules.get("idea_spark")
    if module is not None and getattr(module, "__file__", None) == str(init_path):
        return
    spec = importlib.util.spec_from_file_location(
        "idea_spark",
        init_path,
        submodule_search_locations=[str(root)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load flat Idea-Spark source package")
    module = importlib.util.module_from_spec(spec)
    sys.modules["idea_spark"] = module
    spec.loader.exec_module(module)


_load_flat_source_package()


@pytest.fixture
def temp_idea_spark_db(tmp_path, monkeypatch):
    db_path = tmp_path / "idea_spark.sqlite3"
    monkeypatch.setenv("IDEA_SPARK_DB", str(db_path))
    return db_path
