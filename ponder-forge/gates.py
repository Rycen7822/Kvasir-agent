from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

try:
    from .profiles import get_profile
    from .store import PonderForgeStore
except ImportError:
    from profiles import get_profile
    from store import PonderForgeStore

JsonDict = dict[str, Any]


def _raw(row: JsonDict) -> JsonDict:
    try:
        return json.loads(row.get("raw_json") or "{}")
    except json.JSONDecodeError:
        return {}


def _critical(row: JsonDict, critical_types: tuple[str, ...]) -> bool:
    raw = _raw(row)
    return bool(raw.get("critical")) or float(row.get("importance") or 0.0) >= 0.8 or row.get("assertion_type") in critical_types


def _evidence_by_assertion(store: PonderForgeStore, run_id: str) -> dict[str, list[JsonDict]]:
    grouped: dict[str, list[JsonDict]] = defaultdict(list)
    for evidence in store.list_rows("evidence_items", run_id):
        assertion_id = evidence.get("assertion_id")
        if assertion_id:
            grouped[str(assertion_id)].append(evidence)
    return grouped


def _has_required_groups(evidence: list[JsonDict], groups: tuple[tuple[str, ...], ...]) -> bool:
    evidence_types = {str(item.get("evidence_type")) for item in evidence}
    return all(any(kind in evidence_types for kind in group) for group in groups)


def _profile_specific_gap(profile: str, evidence: list[JsonDict]) -> str | None:
    if profile == "analysis" and not any(item.get("evidence_type") == "metric_output" and item.get("command") for item in evidence):
        return "analysis metric_output.command is required for at least one metric_output evidence item"
    if profile == "math" and any(item.get("evidence_type") == "counterexample" for item in evidence):
        return "math proof gate has unresolved counterexample evidence"
    return None


def _reports_by_id(store: PonderForgeStore, run_id: str) -> dict[str, JsonDict]:
    return {row["report_id"]: row for row in store.list_rows("reports", run_id)}


def _has_independent_accept_verdict(
    store: PonderForgeStore,
    run_id: str,
    assertion: JsonDict,
    reports: dict[str, JsonDict],
) -> bool:
    report = reports.get(str(assertion.get("report_id")))
    producer_task_id = report.get("task_id") if report else None
    for verdict in store.list_rows("verification_verdicts", run_id):
        if verdict.get("target_type") != "assertion" or verdict.get("target_id") != assertion.get("assertion_id"):
            continue
        if verdict.get("verifier_mode") != "independent_review" or verdict.get("verdict") != "accept":
            continue
        if producer_task_id and verdict.get("independent_from_task_id") != producer_task_id:
            continue
        if producer_task_id and verdict.get("reviewer_task_id") == producer_task_id:
            continue
        return True
    return False


def evaluate_gate(store: PonderForgeStore, run_id: str) -> JsonDict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    profile = get_profile(str(run["profile"]))
    assertions = store.list_rows("assertions", run_id)
    evidence_by_assertion = _evidence_by_assertion(store, run_id)
    reports = _reports_by_id(store, run_id)

    critical = [row for row in assertions if _critical(row, profile.critical_assertion_types)]
    accepted_count = 0
    gaps: list[JsonDict] = []
    if not critical:
        gaps.append(
            {
                "gap_type": "missing_critical_assertion",
                "target_id": run_id,
                "reason": "no critical assertions submitted for profile gate",
                "required_assertion_types": profile.critical_assertion_types,
            }
        )
    for assertion in critical:
        if assertion.get("status") == "accepted":
            accepted_count += 1
        evidence = evidence_by_assertion.get(assertion["assertion_id"], [])
        profile_specific_gap = _profile_specific_gap(profile.profile_id, evidence)
        supported = _has_required_groups(evidence, profile.required_evidence_groups) and profile_specific_gap is None
        if not supported:
            gap = {
                "target_id": assertion["assertion_id"],
                "reason": "critical assertion lacks required profile evidence",
                "required_groups": profile.required_evidence_groups,
            }
            if profile_specific_gap:
                gap["profile_specific_reason"] = profile_specific_gap
            gaps.append(gap)
        if not _has_independent_accept_verdict(store, run_id, assertion, reports):
            gaps.append(
                {
                    "gap_type": "missing_independent_verdict",
                    "target_id": assertion["assertion_id"],
                    "reason": "critical assertion lacks accepted independent reviewer verdict",
                }
            )

    metrics = {
        "critical_assertion_count": len(critical),
        "accepted_critical_assertion_count": accepted_count,
        "unsupported_critical_assertions": len(gaps),
        "unresolved_conflicts": 0,
        "independent_review_coverage": 0.0,
        "artifact_reproducibility_coverage": 0.0,
        "final_statement_trace_coverage": 0.0,
        "budget_used": 0,
    }
    status = "passed" if not gaps else "blocked"
    return {
        "status": status,
        "profile": profile.profile_id,
        "finalize_allowed": status == "passed",
        "metrics": metrics,
        "gaps": gaps,
    }


def supported_critical_assertion_ids(store: PonderForgeStore, run_id: str) -> list[str]:
    gate = evaluate_gate(store, run_id)
    if gate["status"] != "passed":
        return []
    run = store.get_run(run_id)
    if not run:
        return []
    profile = get_profile(str(run["profile"]))
    return [
        row["assertion_id"]
        for row in store.list_rows("assertions", run_id)
        if _critical(row, profile.critical_assertion_types)
    ]
