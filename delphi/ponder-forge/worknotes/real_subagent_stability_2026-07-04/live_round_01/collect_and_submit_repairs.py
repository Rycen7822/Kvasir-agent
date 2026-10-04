#!/usr/bin/env python3
"""Collect live gate-gap repair report JSON and submit it through installed Ponder-Forge CLI.

PF-REAL-021/PF-REAL-023 controller helper. It scans Hermes delegation summaries and
state.db for JSON reports returned by live gate_gap_repairer leaf subagents,
validates them against the exact repair batch payload, and optionally records
complete batches through installed `submit-report`.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

RUN_ID = "pf_run_80cb097d3870"
ROOT = Path("/home/xu/project/autosci-delphi/ponder-forge")
ROUND_DIR = ROOT / "worknotes/real_subagent_stability_2026-07-04/live_round_01"
HERMES_HOME = ROOT / "worknotes/real_subagent_stability_2026-07-04/hermes_home_live_01"
PF_CLI = Path("/home/xu/.hermes/plugins/ponder_forge/cli.py")
CACHE_DIR = Path("/home/xu/.hermes/cache/delegation")
STATE_DB = Path("/home/xu/.hermes/state.db")
QUEST_PATH = Path("/home/xu/project/loop/DeepScientist/quests/001")
RESULT_DIR = ROUND_DIR / "repair_results"
SUBMIT_DIR = ROUND_DIR / "repair_submit_outputs"

Json = dict[str, Any]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def json_objects(text: str) -> list[Json]:
    decoder = json.JSONDecoder()
    objects: list[Json] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            objects.append(obj)
    return objects


def task_id_from_goal(goal: str) -> str:
    marker = "PONDER_FORGE_TASK_ID="
    if marker not in goal:
        return ""
    return goal.split(marker, 1)[1].split("]", 1)[0]


def expected_for_batch(batch: str) -> dict[str, Json]:
    path = ROUND_DIR / f"35_repair_batch_{batch}_payload.json"
    payload = load_json(path)
    rows: dict[str, Json] = {}
    for index, task in enumerate(payload.get("tasks") or []):
        task_id = task_id_from_goal(str(task.get("goal") or ""))
        rows[task_id] = {"index": index, "batch": batch, "goal": task.get("goal"), "context": task.get("context")}
    return rows


def looks_like_report(obj: Json, expected: dict[str, Json]) -> bool:
    task_id = str(obj.get("task_id") or "")
    return obj.get("run_id") == RUN_ID and task_id in expected and isinstance(obj.get("assertions"), list)


def scan_candidate_reports(expected: dict[str, Json]) -> dict[str, Json]:
    candidates: dict[str, Json] = {}
    paths = sorted(CACHE_DIR.glob("subagent-summary-*.txt"), key=lambda p: p.stat().st_mtime_ns)
    expected_ids = tuple(expected)
    for path in paths:
        text = path.read_text(errors="replace")
        if RUN_ID not in text or not any(task_id in text for task_id in expected_ids):
            continue
        for obj in json_objects(text):
            if not looks_like_report(obj, expected):
                continue
            obj["_source_ref"] = str(path)
            candidates[str(obj["task_id"])] = obj
    if STATE_DB.exists():
        con = sqlite3.connect(str(STATE_DB))
        try:
            rows = con.execute(
                """
                select id, session_id, role, content
                from messages
                where content like ? and content like '%gate_gap_repairer%' and content like '%assertions%'
                order by id
                """,
                (f"%{RUN_ID}%",),
            ).fetchall()
        finally:
            con.close()
        for message_id, session_id, role, text in rows:
            if not isinstance(text, str) or not any(task_id in text for task_id in expected_ids):
                continue
            for obj in json_objects(text):
                if not looks_like_report(obj, expected):
                    continue
                obj["_source_ref"] = f"state_db:messages:{message_id}:{session_id}:{role}"
                candidates[str(obj["task_id"])] = obj
    return candidates


def validate_report(report: Json, expected: dict[str, Json]) -> list[str]:
    errors: list[str] = []
    task_id = str(report.get("task_id") or "")
    if task_id not in expected:
        return [f"unexpected task_id: {task_id!r}"]
    if report.get("run_id") != RUN_ID:
        errors.append(f"run_id mismatch: {report.get('run_id')!r}")
    if str(report.get("role") or "") != "gate_gap_repairer":
        errors.append(f"role mismatch: {report.get('role')!r}")
    if not str(report.get("title") or "").strip():
        errors.append("title is empty")
    if not str(report.get("summary") or "").strip():
        errors.append("summary is empty")
    assertions = report.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        errors.append("assertions must be a non-empty JSON array")
    else:
        for index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict):
                errors.append(f"assertions[{index}] is not an object")
                continue
            if not str(assertion.get("assertion_type") or assertion.get("type") or "").strip():
                errors.append(f"assertions[{index}] missing assertion_type")
            if not str(assertion.get("text") or assertion.get("statement") or "").strip():
                errors.append(f"assertions[{index}] missing text")
    if not isinstance(report.get("artifacts"), list):
        errors.append("artifacts must be a JSON array; use [] if none")
    return errors


def normalize_report(report: Json, expected_row: Json) -> tuple[Json, list[str]]:
    clean = dict(report)
    notes: list[str] = []
    if not str(clean.get("title") or "").strip():
        target = str(clean.get("target_assertion_id") or "")
        if not target:
            context = str(expected_row.get("context") or "")
            marker = "target_assertion_id="
            if marker in context:
                target = context.split(marker, 1)[1].splitlines()[0].strip()
        clean["title"] = f"Gate gap repair for {target or clean.get('task_id')}"
        notes.append("filled missing title from task metadata")
    return clean, notes


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
    stem = path.stem
    (SUBMIT_DIR / f"{stem}.stdout").write_text(cp.stdout)
    (SUBMIT_DIR / f"{stem}.stderr").write_text(cp.stderr)
    if cp.returncode != 0:
        raise RuntimeError(f"submit-report failed for {path.name}: stdout={cp.stdout[-1000:]!r} stderr={cp.stderr[-1000:]!r}")
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
    parser.add_argument("--batch", default="A", choices=["A", "B", "C", "D", "E"])
    parser.add_argument("--record", action="store_true", help="submit complete validated repair reports through installed CLI")
    args = parser.parse_args()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    expected = expected_for_batch(args.batch)
    candidates = scan_candidate_reports(expected)
    summary: Json = {
        "run_id": RUN_ID,
        "batch": args.batch,
        "expected_report_count": len(expected),
        "found_report_count": len(candidates),
        "missing_task_ids": sorted(set(expected) - set(candidates)),
        "quest_signature": quest_signature(),
        "reports": {},
    }
    all_valid = True
    for task_id, report in sorted(candidates.items(), key=lambda kv: expected[kv[0]]["index"]):
        clean, normalization_notes = normalize_report(report, expected[task_id])
        source_ref = clean.pop("_source_ref", None)
        errors = validate_report(clean, expected)
        path = RESULT_DIR / f"repair_{args.batch}_{expected[task_id]['index']:02d}_{task_id}.json"
        path.write_text(json.dumps(clean, indent=2, ensure_ascii=False, sort_keys=True))
        summary["reports"][task_id] = {
            "index": expected[task_id]["index"],
            "source_ref": source_ref,
            "saved_path": str(path),
            "assertion_count": len(clean.get("assertions") or []),
            "errors": errors,
            "normalization_notes": normalization_notes,
        }
        if errors:
            all_valid = False
    summary["all_found"] = len(candidates) == len(expected)
    summary["all_valid"] = bool(all_valid and summary["all_found"])
    if args.record:
        if not summary["all_valid"]:
            out = ROUND_DIR / f"37_repair_batch_{args.batch}_record_summary.json"
            out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            raise SystemExit(2)
        for task_id, info in sorted(summary["reports"].items(), key=lambda kv: kv[1]["index"]):
            info["submit_result"] = submit_report(Path(info["saved_path"]))
    out = ROUND_DIR / f"37_repair_batch_{args.batch}_{'record' if args.record else 'collect'}_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
