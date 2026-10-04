from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from store import PonderForgeStore


@pytest.fixture
def state(tmp_path):
    store = PonderForgeStore(tmp_path)
    store.initialize()
    return store


@pytest.fixture
def run(state):
    return state.create_run(goal="Research the question", profile="research",
                            config={"team_effort": "max"}, budget={"delegate_batch_size": 20})
