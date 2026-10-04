"""Explicit paired comparisons over saved managed attempts; no scheduling."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import math

from .evidence_contracts import EvidenceError, validate_document
from .research_state import digest, file_hash, within


def request_snapshot(spec, environment, protocol=None, candidate=None):
    result = {"spec": spec, "environment": environment}
    if protocol is not None:
        result["protocol"] = protocol
    if candidate is not None:
        result["candidate"] = candidate
    return result


def protocol_issues(protocol, spec, environment, project):
    validate_document(protocol, "comparison")
    issues = []
    pairs = protocol["pairs"]
    if len({p["pair_id"] for p in pairs}) != len(pairs):
        issues.append("duplicate_pair_id")
    if len({(p["task_id"], p["seed"]) for p in pairs}) != len(pairs):
        issues.append("duplicate_task_seed")
    try:
        declared = datetime.fromisoformat(protocol["declared_at"])
        if declared.tzinfo is None or declared > datetime.now(timezone.utc):
            issues.append("invalid_protocol_time")
    except ValueError:
        issues.append("invalid_protocol_time")
    if protocol["environment_digest"] != digest(environment):
        issues.append("protocol_environment_mismatch")
    if sorted(protocol["datasets"], key=lambda x: x["path"]) != sorted(environment["datasets"], key=lambda x: x["path"]):
        issues.append("protocol_dataset_mismatch")
    if protocol["evaluator"] not in environment["protected_files"]:
        issues.append("protocol_evaluator_mismatch")
    metric = environment["primary_metric"]
    if any(protocol["metric"][k] != metric[k] for k in ("name", "direction")):
        issues.append("protocol_metric_mismatch")
    binding = spec.get("comparison", {})
    pair = next((p for p in pairs if p["pair_id"] == binding.get("pair_id")), None)
    if pair is None or pair["seed"] != spec["seed"]:
        issues.append("protocol_pair_mismatch")
    role = "baseline" if spec["purpose"] == "baseline" else "candidate"
    if spec["method_id"] != protocol["methods"][role]:
        issues.append("protocol_method_mismatch")
    if binding.get("metric_unit") != protocol["metric"]["unit"]:
        issues.append("metric_unit_mismatch")
    if binding.get("metric_selection") != protocol["metric"]["selection"]:
        issues.append("metric_selection_mismatch")
    if spec["resources"]["timeout_seconds"] != protocol["budget"]["timeout_seconds"]:
        issues.append("protocol_budget_mismatch")
    for item in [protocol["evaluator"], *protocol["datasets"], *protocol["method_inputs"]["baseline"], *protocol["method_inputs"]["candidate"]]:
        try:
            if file_hash(within(project, item["path"], exists=True)) != item["sha256"]:
                issues.append("protocol_input_changed")
        except (EvidenceError, OSError):
            issues.append("protocol_input_unavailable")
    return sorted(set(issues))


def compare(service, protocol):
    """Inspect every attempt bound to this exact protocol, including failures."""
    validate_document(protocol, "comparison")
    key = digest(protocol)
    attempts, issues, slots = [], [], defaultdict(list)
    counts = Counter()
    for path in sorted(service.state.path("runs").glob("*/run.json")):
        try:
            record = service.state.read_run(path.parent.name)
        except EvidenceError:
            # An unreadable record cannot silently vanish from the denominator.
            issues.append(f"{path.parent.name}:unreadable_attempt")
            continue
        saved = record.get("protocol")
        if not isinstance(saved, dict) or digest(saved) != key:
            continue
        spec = record["spec"]
        role = "baseline" if spec["purpose"] == "baseline" else "candidate"
        pair_id = spec["comparison"]["pair_id"]
        failures = service.run_issues(record)
        integrity_issues = [issue for issue in failures if issue != "run_not_verified"]
        origin = spec.get("result_origin", {"kind": "unknown"})
        if origin["kind"] in {"cached", "replayed"}:
            failures.append("reused_result_not_independent")
        failures += protocol_issues(protocol, spec, record["environment"], service.state.project)
        row = {"run_id": record["run_id"], "pair_id": pair_id, "role": role,
               "seed": spec["seed"], "seed_evidence": "declared", "status": record["status"],
               "metric": record.get("metric"), "issues": sorted(set(failures)), "integrity_issues": integrity_issues,
               "idempotency_key": record.get("idempotency_key"), "result_origin": origin,
               "independence": "not_assessed",
               "created_at": record["created_at"], "finished_at": record.get("finished_at"),
               "cost": service.observations(record)["cost"]}
        attempts.append(row)
        counts["attempted"] += 1
        counts[record["status"]] += 1
        if not failures:
            slots[(pair_id, role)].append(record)
            counts["valid"] += 1
        else:
            counts["excluded"] += 1
    deltas, paired = [], []
    for pair in protocol["pairs"]:
        baseline = slots[(pair["pair_id"], "baseline")]
        candidate = slots[(pair["pair_id"], "candidate")]
        if len(baseline) != 1 or len(candidate) != 1:
            reason = "ambiguous_pair" if len(baseline) > 1 or len(candidate) > 1 else "missing_pair"
            issues.append(f"{pair['pair_id']}:{reason}")
            continue
        b, c = baseline[0], candidate[0]
        if c["spec"].get("baseline_run_id") != b["run_id"]:
            issues.append(f"{pair['pair_id']}:baseline_pair_mismatch")
            continue
        delta = c["metric"] - b["metric"]
        improvement = delta if protocol["metric"]["direction"] == "maximize" else -delta
        if not math.isfinite(improvement):
            issues.append(f"{pair['pair_id']}:nonfinite_difference")
            continue
        deltas.append(improvement)
        paired.append({**pair, "baseline_run_id": b["run_id"], "candidate_run_id": c["run_id"],
                       "baseline": b["metric"], "candidate": c["metric"], "difference": delta,
                       "directional_improvement": improvement})
    if not attempts:
        issues.append("protocol_not_referenced")
    counts.update(expected_pairs=len(protocol["pairs"]), paired=len(paired),
                  missing_pairs=len(protocol["pairs"]) - len(paired),
                  declared_reused=sum(r["result_origin"]["kind"] in {"cached", "replayed"} for r in attempts),
                  origin_unknown=sum(r["result_origin"]["kind"] == "unknown" for r in attempts))
    walls = [row["cost"].get("managed_wall_seconds") for row in attempts]
    known_walls = [value for value in walls if value is not None]
    evidence = {"protocol_digest": key, "protocol": protocol, "attempts": attempts,
                "denominator": dict(counts), "pairs": paired,
                "descriptive": {"mean_directional_improvement": sum(x / len(deltas) for x in deltas) if deltas else None},
                "budget_basis": "wall_timeout_only", "total_cost": "unknown",
                "managed_attempt_wall_seconds": sum(known_walls),
                "wall_cost_coverage": {"known": len(known_walls), "attempts": len(attempts)},
                "search_cost_completeness": "not_assessed",
                "statistical_support": "not_assessed", "scientific_validity": "not_assessed",
                "registration": "local_snapshot_not_independent_preregistration",
                "timing": protocol["timing"]}
    return sorted(set(issues)), evidence
