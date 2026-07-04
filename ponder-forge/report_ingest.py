from __future__ import annotations

from typing import Any

try:
    from .store import PonderForgeStore
    from .swarm import task_kind
except ImportError:
    from store import PonderForgeStore
    from swarm import task_kind

JsonDict = dict[str, Any]


def _first_nonempty(payload: JsonDict, *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_evidence_payload(payload: JsonDict) -> JsonDict:
    normalized = dict(payload)
    evidence_type = _first_nonempty(normalized, "evidence_type", "type")
    source_ref = _first_nonempty(normalized, "source_ref", "source")
    observation = _first_nonempty(normalized, "quote_or_observation", "summary", "observation")
    artifact_path = _first_nonempty(normalized, "artifact_path", "path")
    if evidence_type is not None:
        normalized["evidence_type"] = str(evidence_type)
    if source_ref is not None:
        normalized["source_ref"] = source_ref
    if observation is not None:
        normalized["quote_or_observation"] = observation
    if artifact_path is not None:
        normalized["artifact_path"] = artifact_path
    return normalized


def _normalize_artifact_payload(payload: JsonDict) -> JsonDict:
    normalized = dict(payload)
    artifact_type = _first_nonempty(normalized, "artifact_type", "kind", "type")
    summary = _first_nonempty(normalized, "summary", "description")
    if artifact_type is not None:
        normalized["artifact_type"] = str(artifact_type)
    if summary is not None:
        normalized["summary"] = summary
    return normalized


def _evidence_refs(payload: JsonDict) -> list[str]:
    refs = payload.get("evidence_refs") or []
    if isinstance(refs, str):
        refs = [refs]
    return [str(ref) for ref in refs]


def _normalize_assertion_payloads(payload: JsonDict) -> list[JsonDict]:
    assertions = [dict(item) for item in (payload.get("assertions") or [])]
    top_level_evidence = payload.get("evidence") or payload.get("evidence_items") or []
    evidence_by_id: dict[str, JsonDict] = {}
    for item in top_level_evidence:
        evidence = _normalize_evidence_payload(dict(item))
        evidence_id = evidence.get("id")
        if evidence_id not in (None, ""):
            evidence_by_id[str(evidence_id)] = evidence

    consumed_evidence_ids: set[str] = set()
    for assertion in assertions:
        assertion_type = _first_nonempty(assertion, "assertion_type", "type")
        text = _first_nonempty(assertion, "text", "statement")
        if assertion_type in (None, ""):
            raise ValueError("assertion is missing assertion_type")
        if text in (None, ""):
            raise ValueError("assertion is missing text")
        assertion["assertion_type"] = str(assertion_type)
        assertion["text"] = str(text)

        nested_evidence = assertion.get("evidence") or []
        if nested_evidence:
            assertion["evidence"] = [_normalize_evidence_payload(dict(item)) for item in nested_evidence]
            continue

        refs = _evidence_refs(assertion)
        if refs:
            missing = [ref for ref in refs if ref not in evidence_by_id]
            if missing:
                raise ValueError(f"missing evidence_refs: {missing}")
            assertion["evidence"] = [dict(evidence_by_id[ref]) for ref in refs]
            consumed_evidence_ids.update(refs)

    if top_level_evidence:
        evidence_ids = {str(item.get("id")) for item in top_level_evidence if item.get("id") not in (None, "")}
        if len(evidence_ids) != len(top_level_evidence):
            raise ValueError("unlinked evidence: top-level evidence requires id plus assertion evidence_refs")
        unlinked = sorted(evidence_ids - consumed_evidence_ids)
        if unlinked:
            raise ValueError(f"unlinked evidence: {unlinked}")
    return assertions


def _normalize_payload(payload: JsonDict) -> JsonDict:
    normalized = dict(payload)
    normalized["assertions"] = _normalize_assertion_payloads(normalized)
    artifacts = normalized.get("artifacts") or []
    if not isinstance(artifacts, list):
        raise ValueError("artifacts must be a JSON array; use [] if there are no artifacts")
    normalized["artifacts"] = [_normalize_artifact_payload(dict(item)) for item in artifacts]
    return normalized


def _edge_relation_for_evidence(item: JsonDict) -> str:
    return "refutes" if item.get("counterevidence") else "supports"


def _ingest_single_report(store: PonderForgeStore, payload: JsonDict) -> JsonDict:
    payload = _normalize_payload(payload)
    run_id = str(payload["run_id"])
    task_id = payload.get("task_id")
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")

    report = store.create_report(
        run_id=run_id,
        task_id=task_id,
        role=str(payload.get("role") or "unknown"),
        title=payload.get("title"),
        summary=str(payload.get("summary") or ""),
        confidence=payload.get("confidence"),
        raw=payload,
    )
    if task_id:
        store.create_edge(
            run_id=run_id,
            src_type="report",
            src_id=report["report_id"],
            dst_type="task",
            dst_id=str(task_id),
            edge_type="produced_by",
        )

    assertion_ids: list[str] = []
    evidence_ids: list[str] = []
    artifact_ids: list[str] = []

    for assertion_payload in payload.get("assertions") or []:
        assertion = store.create_assertion(
            run_id=run_id,
            report_id=report["report_id"],
            profile=str(run["profile"]),
            assertion_type=str(assertion_payload.get("assertion_type") or "claim"),
            text=str(assertion_payload.get("text") or ""),
            importance=float(assertion_payload.get("importance", 0.5)),
            confidence=assertion_payload.get("confidence"),
            raw=assertion_payload,
        )
        assertion_ids.append(assertion["assertion_id"])
        store.create_edge(
            run_id=run_id,
            src_type="assertion",
            src_id=assertion["assertion_id"],
            dst_type="report",
            dst_id=report["report_id"],
            edge_type="derived_from",
        )
        for evidence_payload in assertion_payload.get("evidence") or []:
            evidence = store.create_evidence(
                run_id=run_id,
                report_id=report["report_id"],
                assertion_id=assertion["assertion_id"],
                evidence_type=str(evidence_payload.get("evidence_type") or "observation"),
                source_ref=evidence_payload.get("source_ref"),
                title=evidence_payload.get("title"),
                quote_or_observation=evidence_payload.get("quote_or_observation"),
                locator=evidence_payload.get("locator"),
                source_date=evidence_payload.get("source_date"),
                reliability=float(evidence_payload.get("reliability", 0.5)),
                relevance=float(evidence_payload.get("relevance", 0.5)),
                directness=float(evidence_payload.get("directness", 0.5)),
                freshness=float(evidence_payload.get("freshness", 0.5)),
                counterevidence=bool(evidence_payload.get("counterevidence", False)),
                artifact_path=evidence_payload.get("artifact_path"),
                command=evidence_payload.get("command"),
                exit_code=evidence_payload.get("exit_code"),
                metric=evidence_payload.get("metric"),
                raw=evidence_payload,
            )
            evidence_ids.append(evidence["evidence_id"])
            store.create_edge(
                run_id=run_id,
                src_type="evidence",
                src_id=evidence["evidence_id"],
                dst_type="assertion",
                dst_id=assertion["assertion_id"],
                edge_type=_edge_relation_for_evidence(evidence_payload),
            )

    for artifact_payload in payload.get("artifacts") or []:
        artifact = store.create_artifact(
            run_id=run_id,
            report_id=report["report_id"],
            artifact_type=str(artifact_payload.get("artifact_type") or "artifact"),
            path=artifact_payload.get("path"),
            summary=artifact_payload.get("summary"),
            raw=artifact_payload,
        )
        artifact_ids.append(artifact["artifact_id"])
        store.create_edge(
            run_id=run_id,
            src_type="artifact",
            src_id=artifact["artifact_id"],
            dst_type="report",
            dst_id=report["report_id"],
            edge_type="derived_from",
        )

    return {
        "report_id": report["report_id"],
        "assertion_ids": assertion_ids,
        "evidence_ids": evidence_ids,
        "artifact_ids": artifact_ids,
    }


def _expected_lane_children(store: PonderForgeStore, run_id: str, lane_task_id: str) -> dict[str, JsonDict]:
    children = {}
    for task in store.list_rows("agent_tasks", run_id):
        if task.get("parent_task_id") == lane_task_id and task.get("status") == "planned" and task_kind(task) == "lane_child":
            children[str(task["task_id"])] = task
    return children


def _validate_child_report_ids(child_reports: list[JsonDict]) -> set[str]:
    seen: set[str] = set()
    for report in child_reports:
        task_id = str(report.get("task_id") or "")
        if not task_id:
            raise ValueError("child report is missing task_id")
        if task_id in seen:
            raise ValueError(f"duplicate child report task_id: {task_id}")
        seen.add(task_id)
    return seen


def _ingest_lane_report(store: PonderForgeStore, payload: JsonDict, child_reports: list[JsonDict]) -> JsonDict:
    run_id = str(payload["run_id"])
    lane_task_id = str(payload.get("task_id") or "")
    lane_task = store.get_task(lane_task_id) if lane_task_id else None
    if not lane_task or task_kind(lane_task) != "lane_coordinator":
        raise ValueError("child_reports require a lane coordinator task_id")

    expected_children = _expected_lane_children(store, run_id, lane_task_id)
    reported_ids = _validate_child_report_ids(child_reports)
    for child_id in reported_ids:
        child_task = store.get_task(child_id)
        if not child_task:
            raise ValueError(f"unknown child report task_id: {child_id}")
        if task_kind(child_task) != "lane_child" or child_task.get("parent_task_id") != lane_task_id:
            raise ValueError(f"child report task_id does not belong to lane: {child_id}")

    missing = sorted(set(expected_children) - reported_ids)
    if missing:
        raise ValueError(f"missing child_reports: {missing}")

    child_report_ids: list[str] = []
    for child_report in child_reports:
        child_payload = dict(child_report)
        child_task_id = str(child_payload["task_id"])
        child_task = expected_children[child_task_id]
        child_payload["run_id"] = run_id
        child_payload.setdefault("role", child_task["role"])
        child_result = _ingest_single_report(store, child_payload)
        child_report_ids.append(child_result["report_id"])
        store.update_task_status(child_task_id, "finished")

    lane_payload = dict(payload)
    lane_payload["child_report_ids"] = child_report_ids
    lane_result = _ingest_single_report(store, lane_payload)
    store.update_task_status(lane_task_id, "finished")
    return {**lane_result, "child_report_ids": child_report_ids}


def ingest_report(store: PonderForgeStore, payload: JsonDict) -> JsonDict:
    child_reports = payload.get("child_reports") or []
    if child_reports:
        return _ingest_lane_report(store, payload, [dict(report) for report in child_reports])
    return _ingest_single_report(store, payload)
