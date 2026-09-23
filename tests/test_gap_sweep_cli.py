from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_kactl(*args: str, project_root: Path) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "kactl.py"), "--project-root", str(project_root), *args],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_trial_evaluate_decide_and_queue_reconcile_cli(tmp_path: Path):
    run_kactl("manifest", "init", "--name", "Demo", "--goal", "Improve", "--format", "json", project_root=tmp_path)
    run_kactl("baseline", "confirm", "--id", "b1", "--format", "json", project_root=tmp_path)
    run_kactl("trial", "propose", "--quest-id", "q1", "--idea-id", "i1", "--hypothesis", "h", "--mechanism", "m", "--format", "json", project_root=tmp_path)
    run_kactl("trial", "plan", "T0001", "--metric-contract", "primary", "--novelty", "allow", "--format", "json", project_root=tmp_path)
    run_kactl("trial", "ready", "T0001", "--format", "json", project_root=tmp_path)

    evaluated = run_kactl("trial", "evaluate", "T0001", "--metric", "primary=0.9", "--artifact", "metrics.json", "--format", "json", project_root=tmp_path)
    assert evaluated["trial"]["status"] == "evaluated"
    decided = run_kactl("trial", "decide", "T0001", "--decision", "keep", "--reviewer-verdict", "pass", "--format", "json", project_root=tmp_path)
    assert decided["trial"]["status"] == "kept"

    run_kactl("queue", "submit", "--job-id", "job1", "--command", "python train.py", "--format", "json", project_root=tmp_path)
    leased = run_kactl("queue", "lease-next", "--worker-id", "w1", "--ttl-seconds", "0", "--format", "json", project_root=tmp_path)
    assert leased["job"]["status"] == "leased"
    reconciled = run_kactl("queue", "reconcile", "--format", "json", project_root=tmp_path)
    assert reconciled["jobs"]["job1"]["status"] == "reconcile_required"


def test_stage_reflection_and_novelty_cli(tmp_path: Path):
    run_kactl("journal", "stage-reflection", "--trigger", "two_failures", "--gap", "metric dropped", "--next-source", "review_gap", "--format", "json", project_root=tmp_path)
    run_kactl("journal", "negative", "--trial-id", "T0001", "--idea-id", "I_old", "--failure-reason", "duplicate", "--lesson", "avoid widening layer blindly", "--format", "json", project_root=tmp_path)
    novelty = run_kactl("frontier", "check-novelty", "--idea-id", "I_new", "--mechanism", "avoid widening layer blindly", "--format", "json", project_root=tmp_path)
    assert novelty["decision"] == "block_duplicate"
