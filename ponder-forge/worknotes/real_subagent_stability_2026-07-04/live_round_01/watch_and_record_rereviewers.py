#!/usr/bin/env python3
"""Wait for second-round reviewer verdicts and record only when complete."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path("/home/xu/project/autosci-delphi/ponder-forge")
ROUND_DIR = ROOT / "worknotes/real_subagent_stability_2026-07-04/live_round_01"
COLLECTOR = ROUND_DIR / "collect_and_record_rereviewers.py"
RESULT_PATH = ROUND_DIR / "47_rereviewer_watchdog_result.json"
LOG_PATH = ROUND_DIR / "47_rereviewer_watchdog.log"


def run_collector(record: bool = False) -> dict:
    args = ["python3", str(COLLECTOR)]
    if record:
        args.append("--record")
    cp = subprocess.run(args, cwd=str(ROOT), text=True, capture_output=True)
    with LOG_PATH.open("a") as fh:
        fh.write(f"\n$ {' '.join(args)}\n")
        fh.write(cp.stdout)
        if cp.stderr:
            fh.write("\n[stderr]\n")
            fh.write(cp.stderr)
    if cp.returncode != 0:
        if cp.stdout.strip():
            try:
                return json.loads(cp.stdout)
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"collector failed rc={cp.returncode}: {cp.stderr[-1000:]} {cp.stdout[-1000:]}")
    return json.loads(cp.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=60)
    parser.add_argument("--sleep-seconds", type=float, default=60.0)
    args = parser.parse_args()
    start = time.monotonic()
    LOG_PATH.write_text("")
    snapshot: dict = {}
    for attempt in range(1, args.attempts + 1):
        summary = run_collector(record=False)
        snapshot = {
            "attempt": attempt,
            "expected_reviewer_count": summary.get("expected_reviewer_count"),
            "found_reviewer_count": summary.get("found_reviewer_count"),
            "missing_count": len(summary.get("missing_reviewer_task_ids") or []),
            "all_found": summary.get("all_found"),
            "all_valid": summary.get("all_valid"),
            "verdict_counts": summary.get("verdict_counts"),
        }
        with LOG_PATH.open("a") as fh:
            fh.write("\nSNAPSHOT " + json.dumps(snapshot, sort_keys=True) + "\n")
        if summary.get("all_valid"):
            record_summary = run_collector(record=True)
            result = {
                "attempt": attempt,
                "elapsed_seconds": round(time.monotonic() - start, 2),
                "status": "recorded",
                "record_summary": {
                    "expected_reviewer_count": record_summary.get("expected_reviewer_count"),
                    "found_reviewer_count": record_summary.get("found_reviewer_count"),
                    "all_found": record_summary.get("all_found"),
                    "all_valid": record_summary.get("all_valid"),
                    "verdict_counts": record_summary.get("verdict_counts"),
                    "missing_reviewer_task_ids": record_summary.get("missing_reviewer_task_ids"),
                },
            }
            RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True))
            print(json.dumps(result, sort_keys=True))
            return
        if attempt < args.attempts:
            time.sleep(args.sleep_seconds)
    result = {
        "attempt": args.attempts,
        "elapsed_seconds": round(time.monotonic() - start, 2),
        "status": "timeout_incomplete",
        "last_summary": snapshot,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
