#!/usr/bin/env python3
"""Collect live lane subagent JSON reports and submit them through installed Ponder-Forge CLI.

This is a PF-REAL-021 controller helper. It writes only under the Ponder-Forge
worknotes round directory and the isolated HERMES_HOME. It never writes to the
quest path.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

RUN_ID = "pf_run_80cb097d3870"
ROOT = Path("/home/xu/project/autosci-delphi/ponder-forge")
ROUND_DIR = ROOT / "worknotes/real_subagent_stability_2026-07-04/live_round_01"
HERMES_HOME = ROOT / "worknotes/real_subagent_stability_2026-07-04/hermes_home_live_01"
PF_CLI = Path("/home/xu/.hermes/plugins/ponder_forge/cli.py")
DELEGATIONS_JSON = ROUND_DIR / "03_delegations.json"
CACHE_DIR = Path("/home/xu/.hermes/cache/delegation")
RESULT_DIR = ROUND_DIR / "lane_results"
SUBMIT_DIR = ROUND_DIR / "lane_submit_outputs"
QUEST_PATH = Path("/home/xu/project/loop/DeepScientist/quests/001")

Json = dict[str, Any]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def first_json_object(text: str) -> Json | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def child_manifest_from_context(context: str) -> list[Json]:
    marker = "Child task manifest:"
    start = context.find(marker)
    if start == -1:
        raise ValueError("generated lane context is missing child manifest")
    tail = context[start + len(marker):].lstrip()
    decoder = json.JSONDecoder()
    manifest, _ = decoder.raw_decode(tail)
    if not isinstance(manifest, list):
        raise ValueError("child manifest is not a JSON array")
    return manifest


def expected_lanes() -> dict[str, Json]:
    delegations = load_json(DELEGATIONS_JSON)
    tasks = (delegations.get("delegate_task_payload") or {}).get("tasks") or []
    expected: dict[str, Json] = {}
    for index, task in enumerate(tasks):
        goal = task.get("goal") or ""
        match = re.search(r"PONDER_FORGE_TASK_ID=([^\]\s]+)", goal)
        if not match:
            raise ValueError(f"lane {index} goal has no PONDER_FORGE_TASK_ID")
        task_id = match.group(1)
        expected[task_id] = {
            "index": index,
            "goal": goal,
            "context": task.get("context") or "",
            "child_manifest": child_manifest_from_context(task.get("context") or ""),
        }
    return expected


def scan_candidate_reports(expected: dict[str, Json]) -> dict[str, Json]:
    candidates: dict[str, Json] = {}
    paths = sorted(CACHE_DIR.glob("subagent-summary-*.txt"), key=lambda p: p.stat().st_mtime_ns)
    for path in paths:
        text = path.read_text(errors="replace")
        if RUN_ID not in text:
            continue
        obj = first_json_object(text)
        if not obj:
            continue
        task_id = str(obj.get("task_id") or "")
        if task_id not in expected:
            continue
        obj["_source_cache_path"] = str(path)
        candidates[task_id] = obj
    return candidates


def validate_report(report: Json, expected: dict[str, Json]) -> list[str]:
    errors: list[str] = []
    task_id = str(report.get("task_id") or "")
    if report.get("run_id") != RUN_ID:
        errors.append(f"run_id mismatch: {report.get('run_id')!r}")
    if task_id not in expected:
        errors.append(f"unexpected lane task_id: {task_id!r}")
        return errors
    if str(report.get("role") or "") != "swarm_lane_coordinator":
        errors.append(f"role must be swarm_lane_coordinator, got {report.get('role')!r}")
    if not str(report.get("summary") or "").strip():
        errors.append("summary is empty")
    child_reports = report.get("child_reports")
    if not isinstance(child_reports, list):
        errors.append("child_reports must be a JSON array")
        child_reports = []
    expected_child_ids = {str(item.get("task_id")) for item in expected[task_id]["child_manifest"]}
    actual_child_ids = {str(item.get("task_id")) for item in child_reports if isinstance(item, dict)}
    missing = sorted(expected_child_ids - actual_child_ids)
    extra = sorted(actual_child_ids - expected_child_ids)
    if missing:
        errors.append(f"missing child reports: {missing}")
    if extra:
        errors.append(f"unexpected child reports: {extra}")
    if not isinstance(report.get("assertions"), list):
        errors.append("assertions must be a JSON array")
    if not isinstance(report.get("artifacts"), list):
        errors.append("top-level artifacts must be a JSON array")
    # Analysis profile gate evidence requirements: metric_output with exit_code=0,
    # transform_script or reproduction_log, and sanity_check.
    evidence_types: set[str] = set()
    successful_metric = False
    for assertion in report.get("assertions") or []:
        if not isinstance(assertion, dict):
            continue
        for ev in assertion.get("evidence") or []:
            if not isinstance(ev, dict):
                continue
            etype = str(ev.get("evidence_type") or ev.get("type") or "")
            evidence_types.add(etype)
            if etype == "metric_output" and ev.get("command") and ev.get("exit_code") == 0:
                successful_metric = True
    for child in child_reports:
        if not isinstance(child, dict):
            continue
        for assertion in child.get("assertions") or []:
            if not isinstance(assertion, dict):
                continue
            for ev in assertion.get("evidence") or []:
                if not isinstance(ev, dict):
                    continue
                etype = str(ev.get("evidence_type") or ev.get("type") or "")
                evidence_types.add(etype)
                if etype == "metric_output" and ev.get("command") and ev.get("exit_code") == 0:
                    successful_metric = True
    if "metric_output" not in evidence_types or not successful_metric:
        errors.append("missing successful metric_output evidence with command and exit_code=0")
    if not ({"transform_script", "reproduction_log"} & evidence_types):
        errors.append("missing transform_script or reproduction_log evidence")
    if "sanity_check" not in evidence_types:
        errors.append("missing sanity_check evidence")
    return errors


def submit_report(path: Path) -> Json:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(HERMES_HOME)
    cp = subprocess.run(
        ["python3", str(PF_CLI), "submit-report", "--file", str(path)],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    SUBMIT_DIR.mkdir(parents=True, exist_ok=True)
    (SUBMIT_DIR / f"{path.stem}.stdout").write_text(cp.stdout)
    (SUBMIT_DIR / f"{path.stem}.stderr").write_text(cp.stderr)
    if cp.returncode != 0:
        raise RuntimeError(f"submit-report failed for {path}: stdout={cp.stdout[-1000:]!r} stderr={cp.stderr[-1000:]!r}")
    return json.loads(cp.stdout)


def quest_signature() -> Json:
    count = 0
    total_size = 0
    latest = (-1, "")
    for path in QUEST_PATH.rglob("*"):
        if not path.is_file():
            continue
        st = path.stat()
        count += 1
        total_size += st.st_size
        if st.st_mtime_ns > latest[0]:
            latest = (st.st_mtime_ns, str(path.relative_to(QUEST_PATH)))
    return {"file_count": count, "total_size": total_size, "latest_mtime_ns": latest[0], "latest_path": latest[1]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submit", action="store_true", help="submit validated complete reports through installed CLI")
    args = parser.parse_args()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    expected = expected_lanes()
    candidates = scan_candidate_reports(expected)
    summary: Json = {
        "run_id": RUN_ID,
        "expected_lane_count": len(expected),
        "found_lane_count": len(candidates),
        "missing_lane_task_ids": sorted(set(expected) - set(candidates)),
        "reports": {},
        "quest_signature": quest_signature(),
    }
    all_valid = True
    for task_id, report in sorted(candidates.items(), key=lambda kv: expected[kv[0]]["index"]):
        clean_report = dict(report)
        source_path = clean_report.pop("_source_cache_path", None)
        errors = validate_report(clean_report, expected)
        lane_path = RESULT_DIR / f"lane_{expected[task_id]['index'] + 1:02d}_{task_id}.json"
        lane_path.write_text(json.dumps(clean_report, indent=2, ensure_ascii=False, sort_keys=True))
        summary["reports"][task_id] = {
            "index": expected[task_id]["index"],
            "source_cache_path": source_path,
            "saved_path": str(lane_path),
            "errors": errors,
            "child_report_count": len(clean_report.get("child_reports") or []),
            "assertion_count": len(clean_report.get("assertions") or []),
            "artifact_array": isinstance(clean_report.get("artifacts"), list),
        }
        if errors:
            all_valid = False
        elif args.submit:
            summary["reports"][task_id]["submit_result"] = submit_report(lane_path)
    summary["all_found"] = len(candidates) == len(expected)
    summary["all_valid"] = all_valid and summary["all_found"]
    out = ROUND_DIR / ("07_collect_submit_summary.json" if args.submit else "07_collect_dry_run_summary.json")
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.submit and not summary["all_valid"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
