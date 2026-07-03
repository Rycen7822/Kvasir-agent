from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "benchmarks" / "mini_cases"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gates import evaluate_gate
from planner import plan_run
from report_ingest import ingest_report
from store import PonderForgeStore
from verifier import verify_run


def _load_cli():
    spec = importlib.util.spec_from_file_location("ponder_forge_cli_benchmark", ROOT / "cli.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load cli.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLI = _load_cli()


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def run_case(case: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"pf-{case['profile']}-") as home:
        old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = home
        try:
            start = CLI.start_run(case["goal"], profile=case["profile"])
            store = _store()
            plan = plan_run(store, start["run_id"])
            producer_task = plan["tasks"][0]
            report_payload = dict(case["report"])
            report_payload.update({"run_id": start["run_id"], "task_id": producer_task["task_id"], "role": producer_task["role"]})
            report = ingest_report(store, report_payload)
            assertion_id = report["assertion_ids"][0]
            review = verify_run(store, start["run_id"], {"run_id": start["run_id"], "mode": "independent_review", "target_id": assertion_id})
            reviewer_task = review["reviewer_tasks"][0]
            verify_run(
                store,
                start["run_id"],
                {
                    "run_id": start["run_id"],
                    "mode": "independent_review",
                    "target_id": assertion_id,
                    "reviewer_task_id": reviewer_task["task_id"],
                    "reviewer_role": reviewer_task["role"],
                    "independent_from_task_id": producer_task["task_id"],
                    "verdict": "accept",
                    "confidence": 0.9,
                    "rationale": "mini benchmark fixture review",
                },
            )
            gate = evaluate_gate(store, start["run_id"])
            final = CLI.cmd_finalize(Namespace(run_id=start["run_id"]))
            return {
                "profile": case["profile"],
                "run_id": start["run_id"],
                "gate_status": gate["status"],
                "final_status": final["status"],
                "artifact_paths": final.get("artifact_paths", {}),
            }
        finally:
            if old_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = old_home


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(CASES_DIR.glob("*.json"))]
    results = [run_case(case) for case in cases]
    summary = {
        "cases": results,
        "summary": {
            "total": len(results),
            "final": sum(1 for result in results if result["final_status"] == "final"),
            "blocked": sum(1 for result in results if result["final_status"] == "blocked"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
