"""Exercise offline CLI fixtures. This does not run models or native agents."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def run_case(case: dict, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HERMES_HOME": str(directory / "state")}
    def invoke(*args):
        result = subprocess.run([sys.executable, str(ROOT / "cli.py"), *args],
                                env=env, text=True, capture_output=True, check=False)
        payload = json.loads(result.stdout)
        if result.returncode or not payload["success"]:
            raise RuntimeError(f"CLI fixture failed: {args[0]}: {payload}")
        return payload
    def write(name, payload):
        path = directory / name
        path.write_text(json.dumps(payload, ensure_ascii=False))
        return str(path)
    started_at = time.monotonic()
    run = invoke("start", "--goal", case["goal"], "--profile", case["profile"],
                 "--team-effort", case["team_effort"])
    rid = run["run_id"]
    policy = invoke("plan", "--run-id", rid)
    if not policy["coordinator_prompt"].endswith(f"<team_effort>{case['team_effort']}</team_effort>"):
        raise RuntimeError("incorrect strategy level")
    board_file = write("board.json", {"tasks": [{"description": case["goal"]}]})
    board = invoke("plan", "--run-id", rid, "--file", board_file)["task_board"][0]
    assignments_file = write("assignments.json", {"tasks": [{"agent": "fixture_researcher",
        "prompt": case["goal"], "task_ids": [board["id"]]}]})
    task = invoke("delegations", "--run-id", rid, "--file", assignments_file)["assignments"][0]
    report_file = write("report.json", {"run_id": rid, "task_id": task["task_id"], **case["report"]})
    invoke("submit-report", "--file", report_file)
    if invoke("gate", "--run-id", rid)["pass"]:
        raise RuntimeError("returned report unexpectedly resolved the question")
    draft = directory / "draft.md"
    draft.write_text(case["draft"])
    verifier = invoke("verify", "--run-id", rid, "--mode", "final", "--file", str(draft))["assignments"][0]
    verification = write("verification.json", {"run_id": rid, "task_id": verifier["task_id"],
        "content": "OFFLINE FIXTURE ONLY: expected verification reply; no independent research executed."})
    invoke("submit-report", "--file", verification)
    invoke("plan", "--run-id", rid, "--file", write("resolution.json", {
        "tasks": [{"id": board["id"], "resolution": "resolved"}]}))
    final = invoke("finalize", "--run-id", rid, "--file", str(draft))
    return {"profile": case["profile"], "team_effort": case["team_effort"],
            "run_id": rid, "final_status": final["status"], "artifact_paths": final["artifact_paths"],
            "elapsed_seconds": round(time.monotonic() - started_at, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cases = [json.loads(path.read_text()) for path in sorted((ROOT / "benchmarks/mini_cases").glob("*.json"))]
    results = [run_case(case, args.output.parent / "offline-cases" / case["profile"]) for case in cases]
    summary = {"proof": "offline CLI fixtures; no model or native agent execution", "cases": results,
               "summary": {"total": len(results), "final": sum(x["final_status"] == "final" for x in results)}}
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
