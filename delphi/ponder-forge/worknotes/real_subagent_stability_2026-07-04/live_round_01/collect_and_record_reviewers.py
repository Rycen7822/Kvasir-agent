#!/usr/bin/env python3
"""Collect live reviewer verdict JSON and record them through installed Ponder-Forge CLI.

PF-REAL-021 controller helper. It scans Hermes delegation summaries for reviewer
JSON returned by live reviewer leaf subagents, validates them against the exact
reviewer manifest, and optionally records complete verdicts through installed
`verify --mode independent_review`.
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
MANIFEST_PATH = ROUND_DIR / "16_reviewer_dispatch_manifest.json"
RESULT_DIR = ROUND_DIR / "reviewer_results"
RECORD_DIR = ROUND_DIR / "reviewer_record_outputs"
QUEST_PATH = Path("/home/xu/project/loop/DeepScientist/quests/001")

Json = dict[str, Any]


def parse_confidence(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)
    raise TypeError(f"confidence is not numeric: {value!r}")


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


def manifest_by_reviewer_task() -> dict[str, Json]:
    manifest = load_json(MANIFEST_PATH)
    rows = []
    for batch in manifest.get("batches") or []:
        rows.extend(batch)
    return {str(row["reviewer_task_id"]): row for row in rows}


def scan_candidate_verdicts(expected: dict[str, Json]) -> dict[str, Json]:
    candidates: dict[str, Json] = {}
    paths = sorted(CACHE_DIR.glob("subagent-summary-*.txt"), key=lambda p: p.stat().st_mtime_ns)
    for path in paths:
        text = path.read_text(errors="replace")
        if RUN_ID not in text or "reviewer_task_id" not in text:
            continue
        for obj in json_objects(text):
            reviewer_task_id = str(obj.get("reviewer_task_id") or "")
            if reviewer_task_id not in expected:
                continue
            obj["_source_ref"] = str(path)
            candidates[reviewer_task_id] = obj
    if STATE_DB.exists():
        con = sqlite3.connect(str(STATE_DB))
        try:
            rows = con.execute(
                """
                select id, session_id, role, content
                from messages
                where content like ? and content like '%reviewer_task_id%' and content like '%verdict%'
                order by id
                """,
                (f"%{RUN_ID}%",),
            ).fetchall()
        finally:
            con.close()
        for message_id, session_id, role, text in rows:
            if not isinstance(text, str):
                continue
            for obj in json_objects(text):
                reviewer_task_id = str(obj.get("reviewer_task_id") or "")
                if reviewer_task_id not in expected:
                    continue
                obj["_source_ref"] = f"state_db:messages:{message_id}:{session_id}:{role}"
                candidates[reviewer_task_id] = obj
    return candidates


def validate_verdict(verdict: Json, expected: dict[str, Json]) -> list[str]:
    errors: list[str] = []
    reviewer_task_id = str(verdict.get("reviewer_task_id") or "")
    exp = expected.get(reviewer_task_id)
    if not exp:
        return [f"unexpected reviewer_task_id: {reviewer_task_id!r}"]
    if verdict.get("run_id") != RUN_ID:
        errors.append(f"run_id mismatch: {verdict.get('run_id')!r}")
    if str(verdict.get("target_id") or "") != str(exp.get("target_id") or ""):
        errors.append(f"target_id mismatch: {verdict.get('target_id')!r} != {exp.get('target_id')!r}")
    if str(verdict.get("independent_from_task_id") or "") != str(exp.get("independent_from_task_id") or ""):
        errors.append(
            f"independent_from_task_id mismatch: {verdict.get('independent_from_task_id')!r} != {exp.get('independent_from_task_id')!r}"
        )
    if str(verdict.get("reviewer_role") or "") != str(exp.get("reviewer_role") or ""):
        errors.append(f"reviewer_role mismatch: {verdict.get('reviewer_role')!r} != {exp.get('reviewer_role')!r}")
    if str(verdict.get("verdict") or "").lower() not in {"accept", "reject", "revise"}:
        errors.append(f"invalid verdict: {verdict.get('verdict')!r}")
    try:
        confidence = parse_confidence(verdict.get("confidence"))
    except (TypeError, ValueError):
        errors.append(f"invalid confidence: {verdict.get('confidence')!r}")
    else:
        if not 0 <= confidence <= 1:
            errors.append(f"confidence out of range: {confidence}")
    if not str(verdict.get("rationale") or "").strip():
        errors.append("rationale is empty")
    if "required_actions" in verdict and not isinstance(verdict.get("required_actions"), list):
        errors.append("required_actions must be a JSON array when present")
    return errors


def record_verdict(verdict: Json) -> Json:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(HERMES_HOME)
    args = [
        "python3",
        str(PF_CLI),
        "verify",
        "--run-id",
        RUN_ID,
        "--mode",
        "independent_review",
        "--target-id",
        str(verdict["target_id"]),
        "--reviewer-task-id",
        str(verdict["reviewer_task_id"]),
        "--reviewer-role",
        str(verdict.get("reviewer_role") or "repro_reviewer"),
        "--independent-from-task-id",
        str(verdict.get("independent_from_task_id") or ""),
        "--verdict",
        str(verdict["verdict"]).lower(),
        "--confidence",
        str(parse_confidence(verdict.get("confidence"))),
        "--rationale",
        str(verdict.get("rationale") or ""),
    ]
    cp = subprocess.run(args, cwd=str(ROOT), env=env, text=True, capture_output=True)
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stem = str(verdict["reviewer_task_id"])
    (RECORD_DIR / f"{stem}.stdout").write_text(cp.stdout)
    (RECORD_DIR / f"{stem}.stderr").write_text(cp.stderr)
    if cp.returncode != 0:
        raise RuntimeError(f"verify record failed for {stem}: stdout={cp.stdout[-1000:]!r} stderr={cp.stderr[-1000:]!r}")
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
    parser.add_argument("--record", action="store_true", help="record complete validated verdicts through installed CLI")
    args = parser.parse_args()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    expected = manifest_by_reviewer_task()
    candidates = scan_candidate_verdicts(expected)
    summary: Json = {
        "run_id": RUN_ID,
        "expected_reviewer_count": len(expected),
        "found_reviewer_count": len(candidates),
        "missing_reviewer_task_ids": sorted(set(expected) - set(candidates)),
        "verdict_counts": {},
        "reviewers": {},
        "quest_signature": quest_signature(),
    }
    all_valid = True
    for reviewer_task_id, verdict in sorted(candidates.items(), key=lambda kv: expected[kv[0]]["index"]):
        clean = dict(verdict)
        source_path = clean.pop("_source_ref", None)
        errors = validate_verdict(clean, expected)
        path = RESULT_DIR / f"reviewer_{expected[reviewer_task_id]['index']:02d}_{reviewer_task_id}.json"
        path.write_text(json.dumps(clean, indent=2, ensure_ascii=False, sort_keys=True))
        v = str(clean.get("verdict") or "").lower()
        summary["verdict_counts"][v] = summary["verdict_counts"].get(v, 0) + 1
        summary["reviewers"][reviewer_task_id] = {
            "index": expected[reviewer_task_id]["index"],
            "target_id": expected[reviewer_task_id]["target_id"],
            "source_cache_path": source_path,
            "saved_path": str(path),
            "verdict": v,
            "confidence": clean.get("confidence"),
            "errors": errors,
        }
        if errors:
            all_valid = False
    summary["all_found"] = len(candidates) == len(expected)
    summary["all_valid"] = bool(all_valid and summary["all_found"])
    if args.record:
        if not summary["all_valid"]:
            (ROUND_DIR / "18_reviewer_record_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            raise SystemExit(2)
        for reviewer_task_id, info in sorted(summary["reviewers"].items(), key=lambda kv: kv[1]["index"]):
            verdict = load_json(Path(info["saved_path"]))
            info["record_result"] = record_verdict(verdict)
    out = ROUND_DIR / ("18_reviewer_record_summary.json" if args.record else "18_reviewer_collect_summary.json")
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
