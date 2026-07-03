from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from profiles import PROFILE_IDS

ROOT = Path(__file__).resolve().parents[1]
MINI_CASES = ROOT / "benchmarks" / "mini_cases"


def test_mini_cases_cover_all_profiles_and_required_contract():
    paths = sorted(MINI_CASES.glob("*.json"))
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    assert {case["profile"] for case in cases} == set(PROFILE_IDS)
    for case in cases:
        assert case["goal"]
        assert case["report"]["summary"]
        assert case["report"]["assertions"]
        assertion = case["report"]["assertions"][0]
        assert assertion["critical"] is True
        assert assertion["evidence"]
        assert case["expected_status"] == "final"


def test_mini_benchmark_script_runs_all_cases(tmp_path):
    output = tmp_path / "summary.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_mini_benchmark.py"), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["summary"]["total"] == len(PROFILE_IDS)
    assert summary["summary"]["final"] == len(PROFILE_IDS)
    assert all(case["final_status"] == "final" for case in summary["cases"])


def test_smoke_report_template_exists_and_has_metrics():
    text = (ROOT / "worknotes" / "ponder_forge_smoke_report_template.md").read_text(encoding="utf-8")
    for term in ("unsupported_assertion_rate", "blocked_final_attempts", "successful_finalizations", "live_delegate_status"):
        assert term in text
