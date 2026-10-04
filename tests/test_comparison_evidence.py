"""Real paired runs and independent mismatch/denominator fault probes."""
import json
from pathlib import Path

import pytest

from kvasir_agent.services.evidence import EvidenceService
from kvasir_agent.services.evidence_contracts import EvidenceError
from kvasir_agent.services.research_state import now
from test_evidence_v3 import project, finish, write


def protocol_for(project):
    root, state, spec = project
    env = json.loads((root / "environment.json").read_text())
    protocol = {"schema_version": 1, "protocol_id": "paired", "declared_at": now(), "timing": "prospective",
                "environment_id": env["env_id"], "dataset_id": "data", "split": "heldout",
                "datasets": env["datasets"], "evaluator": env["protected_files"][0],
                "metric": {"name": "score", "unit": "score", "direction": "maximize", "selection": "prespecified"},
                "methods": {"baseline": "base", "candidate": "candidate"},
                "method_inputs": {"baseline": env["protected_files"], "candidate": env["protected_files"]},
                "budget": {"basis": "wall_timeout", "timeout_seconds": 10},
                "pairs": [{"pair_id": f"p-{seed}", "task_id": "task", "seed": seed} for seed in (1, 2)],
                "failure_policy": "require_all_pairs", "selection_rule": "unique_valid_attempt", "statistics": "descriptive_only"}
    write(root / "protocol.json", protocol)
    return protocol


def bound_run(project, seed, purpose, key, baseline=None, change=None):
    root, state, original = project
    spec = {**original, "schema_version": 2, "seed": seed, "purpose": purpose,
            "method_id": "base" if purpose == "baseline" else "candidate",
            "comparison": {"protocol_path": "protocol.json", "pair_id": f"p-{seed}",
                           "metric_unit": "score", "metric_selection": "prespecified"}}
    if baseline:
        spec["baseline_run_id"] = baseline
    if change:
        change(spec)
    write(root / f"{key}.json", spec)
    run = EvidenceService(str(root)).run(f"{key}.json", key)
    finish(state, run["run_id"])
    return run["run_id"]


def check(project):
    root, state, _ = project
    write(root / "check.json", {"schema_version": 2, "target": "comparison", "protocol_path": "protocol.json"})
    result = EvidenceService(str(root)).check("check.json")
    return result, json.loads(Path(result["report_path"]).read_text())["evidence"][0]


def test_distinct_seed_baselines_pair_and_all_attempts_remain_visible(project):
    protocol_for(project)
    for seed in (1, 2):
        baseline = bound_run(project, seed, "baseline", f"base-{seed}")
        bound_run(project, seed, "experiment", f"candidate-{seed}", baseline)
    result, report = check(project)
    assert result["ok"], result
    assert report["denominator"]["attempted"] == 4
    assert report["denominator"]["paired"] == 2
    assert len({p["baseline_run_id"] for p in report["pairs"]}) == 2
    assert report["descriptive"]["mean_directional_improvement"] == 0
    assert report["statistical_support"] == "not_assessed"
    assert all(row["seed_evidence"] == "declared" for row in report["attempts"])


@pytest.mark.parametrize("field,value", [("metric_unit", "percent"), ("metric_selection", "best"), ("pair_id", "missing")])
def test_protocol_binding_mismatch_rejects_before_launch(project, field, value):
    protocol_for(project)
    with pytest.raises(EvidenceError) as exc:
        bound_run(project, 1, "baseline", "bad", change=lambda s: s["comparison"].update({field: value}))
    assert exc.value.kind == "invalid_comparison"
    assert not project[1].path("runs").exists()


def test_missing_pair_duplicate_valid_and_failed_attempt_have_explicit_denominators(project):
    protocol_for(project)
    b = bound_run(project, 1, "baseline", "base")
    bound_run(project, 1, "experiment", "candidate", b)
    result, report = check(project)
    assert result["ok"] and result["status"] == "failed" and "p-2:missing_pair" in result["issues"]
    bound_run(project, 1, "experiment", "duplicate", b)
    bound_run(project, 2, "baseline", "failed", change=lambda s: s.update(command=[s["command"][0], "-c", "raise SystemExit(2)"]))
    result, report = check(project)
    assert "p-1:ambiguous_pair" in result["issues"]
    assert report["denominator"]["attempted"] == 4
    assert report["denominator"]["failed"] == 1
    assert report["denominator"]["excluded"] == 1
    assert len(report["attempts"]) == 4
