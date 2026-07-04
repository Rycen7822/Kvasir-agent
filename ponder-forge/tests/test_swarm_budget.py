from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from swarm import SwarmBudget, normalize_swarm_budget

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli.py"


def _run_cli(tmp_path: Path, *args: str) -> dict:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.stdout.strip(), result.stderr
    payload = json.loads(result.stdout)
    payload["returncode"] = result.returncode
    return payload


def test_swarm_budget_defaults_to_8x4():
    budget = normalize_swarm_budget({})

    assert budget == SwarmBudget(top_level_runs=8, child_concurrency_per_lane=4, delegate_batch_size=20)


def test_swarm_budget_accepts_explicit_lane_count_and_child_concurrency():
    budget = normalize_swarm_budget({"top_level_runs": 12, "child_concurrency_per_lane": 6, "delegate_batch_size": 5})

    assert budget.top_level_runs == 12
    assert budget.child_concurrency_per_lane == 6
    assert budget.delegate_batch_size == 5


@pytest.mark.parametrize(
    "payload",
    [
        {"top_level_runs": 0, "subagents_per_run": 4},
        {"top_level_runs": 8, "child_concurrency_per_lane": -1},
        {"top_level_runs": "8", "child_concurrency_per_lane": 4},
        {"max_tasks_per_wave": 3},
        {"top_level_runs": 8, "child_concurrency_per_lane": 4, "extra": 1},
    ],
)
def test_swarm_budget_rejects_invalid_or_retired_keys(payload):
    with pytest.raises(ValueError):
        normalize_swarm_budget(payload)


def test_cli_start_rejects_retired_budget_key_with_hint(tmp_path):
    payload = _run_cli(tmp_path, "start", "--goal", "research source notes", "--budget-json", '{"max_tasks_per_wave": 2}')

    assert payload["success"] is False
    assert payload["returncode"] == 1
    assert "max_tasks_per_wave" in payload["error"]
    assert "top_level_runs" in payload["hint"]
    assert "child_concurrency_per_lane" in payload["hint"]


def test_cli_start_rejects_old_subagents_per_run_key_with_hint(tmp_path):
    payload = _run_cli(
        tmp_path,
        "start",
        "--goal",
        "research source notes",
        "--budget-json",
        '{"subagents_per_run": 4}',
    )

    assert payload["success"] is False
    assert payload["returncode"] == 1
    assert "subagents_per_run" in payload["error"]
    assert "child_concurrency_per_lane" in payload["hint"]
