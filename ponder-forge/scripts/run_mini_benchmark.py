from __future__ import annotations

import argparse
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "benchmarks" / "mini_cases"


def load_tools():
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("ponder_forge_benchmark_tools", ROOT / "tools.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tools.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HANDLERS


def call(handlers: dict, name: str, args: dict) -> dict:
    result = json.loads(handlers[name](args))
    if not result.get("success"):
        raise RuntimeError(f"{name} failed: {result}")
    return result


def run_case(handlers: dict, case: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"pf-{case['profile']}-") as home:
        old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = home
        try:
            start = call(handlers, "ponder_forge_start", {"goal": case["goal"], "profile": case["profile"]})
            plan = call(handlers, "ponder_forge_plan", {"run_id": start["run_id"]})
            producer_task = plan["tasks"][0]
            report_payload = dict(case["report"])
            report_payload.update({"run_id": start["run_id"], "task_id": producer_task["task_id"], "role": producer_task["role"]})
            report = call(handlers, "ponder_forge_report_submit", report_payload)
            assertion_id = report["assertion_ids"][0]
            review = call(handlers, "ponder_forge_verify", {"run_id": start["run_id"], "mode": "independent_review", "target_id": assertion_id})
            reviewer_task = review["reviewer_tasks"][0]
            call(
                handlers,
                "ponder_forge_verify",
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
            gate = call(handlers, "ponder_forge_gate_status", {"run_id": start["run_id"]})
            final = call(handlers, "ponder_forge_finalize", {"run_id": start["run_id"]})
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
    handlers = load_tools()
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(CASES_DIR.glob("*.json"))]
    results = [run_case(handlers, case) for case in cases]
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
