#!/usr/bin/env python3
"""Watch one repair batch until complete, then record it through installed Ponder-Forge CLI.

Controller helper for PF-REAL-021/PF-REAL-023. It is intentionally batch-scoped
so obsolete reviewer watchdogs can be killed without affecting repair progress.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path("/home/xu/project/autosci-delphi/ponder-forge")
ROUND_DIR = ROOT / "worknotes/real_subagent_stability_2026-07-04/live_round_01"
COLLECTOR = ROUND_DIR / "collect_and_submit_repairs.py"


def load_summary(batch: str) -> dict[str, Any]:
    return json.loads((ROUND_DIR / f"37_repair_batch_{batch}_collect_summary.json").read_text())


def compact(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch": summary.get("batch"),
        "expected_report_count": summary.get("expected_report_count"),
        "found_report_count": summary.get("found_report_count"),
        "all_found": summary.get("all_found"),
        "all_valid": summary.get("all_valid"),
        "missing_task_ids": summary.get("missing_task_ids"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="A", choices=["A", "B", "C", "D", "E"])
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--sleep-seconds", type=int, default=60)
    args = parser.parse_args()

    log_path = ROUND_DIR / f"38_repair_batch_{args.batch}_watchdog.log"
    result_path = ROUND_DIR / f"38_repair_batch_{args.batch}_watchdog_result.json"
    start = time.time()
    last: dict[str, Any] | None = None

    for attempt in range(1, args.attempts + 1):
        cp = subprocess.run(
            ["python3", str(COLLECTOR), "--batch", args.batch],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        try:
            summary = load_summary(args.batch)
        except Exception as exc:  # pragma: no cover - controller utility
            result = {
                "status": "collect_summary_unreadable",
                "batch": args.batch,
                "attempt": attempt,
                "elapsed_seconds": round(time.time() - start, 2),
                "returncode": cp.returncode,
                "stdout_tail": cp.stdout[-2000:],
                "stderr_tail": cp.stderr[-2000:],
                "error": repr(exc),
            }
            result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 1
        last = summary
        row = {
            "stamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "attempt": attempt,
            "returncode": cp.returncode,
            **compact(summary),
        }
        with log_path.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

        if summary.get("all_valid"):
            record_cp = subprocess.run(
                ["python3", str(COLLECTOR), "--batch", args.batch, "--record"],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            if record_cp.returncode != 0:
                result = {
                    "status": "record_failed",
                    "batch": args.batch,
                    "attempt": attempt,
                    "elapsed_seconds": round(time.time() - start, 2),
                    "collect_summary": compact(summary),
                    "returncode": record_cp.returncode,
                    "stdout_tail": record_cp.stdout[-3000:],
                    "stderr_tail": record_cp.stderr[-3000:],
                }
                result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                return 1
            record_summary_path = ROUND_DIR / f"37_repair_batch_{args.batch}_record_summary.json"
            record_summary = json.loads(record_summary_path.read_text())
            result = {
                "status": "recorded",
                "batch": args.batch,
                "attempt": attempt,
                "elapsed_seconds": round(time.time() - start, 2),
                "record_summary": compact(record_summary),
            }
            result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0

        if attempt < args.attempts:
            time.sleep(args.sleep_seconds)

    result = {
        "status": "timeout_incomplete",
        "batch": args.batch,
        "attempts": args.attempts,
        "elapsed_seconds": round(time.time() - start, 2),
        "last_summary": compact(last or {}),
    }
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
