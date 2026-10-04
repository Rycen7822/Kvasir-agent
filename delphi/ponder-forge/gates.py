from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

try:
    from .profiles import get_profile
    from .store import PonderForgeStore
    from .swarm import swarm_topology_status
except ImportError:
    from profiles import get_profile
    from store import PonderForgeStore
    from swarm import swarm_topology_status

JsonDict = dict[str, Any]


def _raw(row: JsonDict) -> JsonDict:
    try:
        return json.loads(row.get("raw_json") or "{}")
    except json.JSONDecodeError:
        return {}


def _critical(row: JsonDict, critical_types: tuple[str, ...]) -> bool:
    raw = _raw(row)
    return bool(raw.get("critical")) or float(row.get("importance") or 0.0) >= 0.8 or row.get("assertion_type") in critical_types


def _active_for_gate(row: JsonDict) -> bool:
    return str(row.get("status") or "unverified") not in {"needs_revision", "rejected", "superseded"}


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


def _successful_exit_code(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if value == 0:
        return True
    if isinstance(value, str):
        try:
            return int(value.strip()) == 0
        except ValueError:
            return False
    return False


def _has_successful_evidence(evidence: list[JsonDict], *types: str) -> bool:
    type_set = set(types)
    for item in evidence:
        if item.get("evidence_type") not in type_set:
            continue
        if item.get("evidence_type") == "passing_test":
            return True
        if item.get("command") and _successful_exit_code(item.get("exit_code")):
            return True
    return False


def _unresolved_counterexample(item: JsonDict) -> bool:
    if item.get("evidence_type") != "counterexample":
        return False
    raw = _raw(item)
    if item.get("counterevidence") or raw.get("counterevidence"):
        return True
    if raw.get("resolved") is True or raw.get("status") in {"resolved", "none_found", "negative"}:
        return False
    observation = str(item.get("quote_or_observation") or raw.get("quote_or_observation") or "").lower()
    if any(term in observation for term in ("found none", "no counterexample", "none found", "resolved")):
        return False
    return True


def _profile_specific_gap(profile: str, evidence: list[JsonDict]) -> str | None:
    if profile == "analysis" and not any(
        item.get("evidence_type") == "metric_output" and item.get("command") and _successful_exit_code(item.get("exit_code"))
        for item in evidence
    ):
        return "analysis metric_output.command and exit_code=0 are required for at least one metric_output evidence item"
    if profile == "coding" and not _has_successful_evidence(evidence, "passing_test", "execution_log"):
        return "coding gate requires successful execution evidence: passing_test or execution_log.exit_code=0"
    if profile == "math" and any(_unresolved_counterexample(item) for item in evidence):
        return "math proof gate has unresolved counterexample evidence"
    return None


def _reports_by_id(store: PonderForgeStore, run_id: str) -> dict[str, JsonDict]:
    return {row["report_id"]: row for row in store.list_rows("reports", run_id)}


def _artifacts_by_report(store: PonderForgeStore, run_id: str) -> dict[str, list[JsonDict]]:
    grouped: dict[str, list[JsonDict]] = defaultdict(list)
    for artifact in store.list_rows("artifacts", run_id):
        report_id = artifact.get("report_id")
        if report_id:
            grouped[str(report_id)].append(artifact)
    return grouped


def _incomplete_gate_gap_repair_task_ids(tasks: list[JsonDict]) -> list[str]:
    incomplete: list[str] = []
    for task in tasks:
        raw = _raw(task)
        if raw.get("reconcile_mode") != "gate_gap_repair":
            continue
        if task.get("status") != "finished":
            incomplete.append(str(task["task_id"]))
    return incomplete


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
    artifacts_by_report = _artifacts_by_report(store, run_id)

    critical = [row for row in assertions if _active_for_gate(row) and _critical(row, profile.critical_assertion_types)]
    accepted_count = 0
    supported_count = 0
    independent_accept_count = 0
    artifact_backed_count = 0
    final_traceable_count = 0
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
        if supported:
            supported_count += 1
        report = reports.get(str(assertion.get("report_id")))
        report_id = str(report.get("report_id")) if report else ""
        if report_id and artifacts_by_report.get(report_id):
            artifact_backed_count += 1
        if not supported:
            gap = {
                "gap_type": "missing_profile_evidence",
                "target_id": assertion["assertion_id"],
                "reason": "critical assertion lacks required profile evidence",
                "required_groups": profile.required_evidence_groups,
            }
            if profile_specific_gap:
                gap["profile_specific_reason"] = profile_specific_gap
            gaps.append(gap)
        has_independent_accept = _has_independent_accept_verdict(store, run_id, assertion, reports)
        if has_independent_accept:
            independent_accept_count += 1
        if supported and has_independent_accept:
            final_traceable_count += 1
        if not has_independent_accept:
            gaps.append(
                {
                    "gap_type": "missing_independent_verdict",
                    "target_id": assertion["assertion_id"],
                    "reason": "critical assertion lacks accepted independent reviewer verdict",
                }
            )

    agent_tasks = store.list_rows("agent_tasks", run_id)
    swarm_topology = swarm_topology_status(agent_tasks)
    if swarm_topology["is_swarm_run"] and not swarm_topology["complete"]:
        gaps.append(
            {
                "gap_type": "incomplete_swarm_topology",
                "target_id": run_id,
                "reason": "all lane coordinator and lane child tasks must finish before finalization",
                "incomplete_task_ids": swarm_topology["incomplete_task_ids"],
            }
        )
    incomplete_gate_gap_repairs = _incomplete_gate_gap_repair_task_ids(agent_tasks)
    if incomplete_gate_gap_repairs:
        gaps.append(
            {
                "gap_type": "incomplete_gate_gap_repairs",
                "target_id": run_id,
                "reason": "gate gap repair tasks must finish before finalization",
                "incomplete_task_ids": incomplete_gate_gap_repairs,
            }
        )

    critical_count = len(critical)
    coverage_denominator = float(critical_count) if critical_count else 1.0
    metrics = {
        "critical_assertion_count": critical_count,
        "accepted_critical_assertion_count": accepted_count,
        "supported_critical_assertion_count": supported_count,
        "unsupported_critical_assertions": critical_count - supported_count,
        "blocking_gap_count": len(gaps),
        "unresolved_conflicts": 0,
        "independent_review_coverage": independent_accept_count / coverage_denominator if critical_count else 0.0,
        "artifact_reproducibility_coverage": artifact_backed_count / coverage_denominator if critical_count else 0.0,
        "final_statement_trace_coverage": final_traceable_count / coverage_denominator if critical_count else 0.0,
        "budget_used": 0,
    }
    status = "passed" if not gaps else "blocked"
    return {
        "status": status,
        "profile": profile.profile_id,
        "finalize_allowed": status == "passed",
        "metrics": metrics,
        "swarm_topology": swarm_topology,
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
        if _active_for_gate(row) and _critical(row, profile.critical_assertion_types)
    ]
