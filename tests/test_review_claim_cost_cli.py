from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_csctl(*args: str, project_root: Path) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "csctl.py"), "--project-root", str(project_root), *args],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_review_claim_and_cost_cli_minimal_surface(tmp_path: Path):
    review = run_csctl(
        "review", "create",
        "--claim-text", "Claim token=abc123",
        "--trial-id", "T0001",
        "--artifact-path", "DeepScientist/trials/T0001/metrics.json",
        "--verdict", "pass",
        "--notes", "ok",
        "--format", "json",
        project_root=tmp_path,
    )
    assert review["review"]["read_only"] is True
    assert "abc123" not in json.dumps(review)

    claim = run_csctl(
        "claim", "upsert",
        "--claim-id", "C1",
        "--text", "Method improves accuracy",
        "--supporting-trial-id", "T0001",
        "--metric", "accuracy=0.91",
        "--artifact-path", "DeepScientist/trials/T0001/metrics.json",
        "--reviewer-verdict", "pass",
        "--format", "json",
        project_root=tmp_path,
    )
    assert claim["claim"]["status"] == "result_claim"

    cost = run_csctl("cost", "check", "--action-class", "GPU/cloud job", "--estimated-cost-usd", "2.5", "--daily-cap-usd", "1.0", "--format", "json", project_root=tmp_path)
    assert cost["decision"] == "blocked_budget"
