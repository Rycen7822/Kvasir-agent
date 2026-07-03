from __future__ import annotations

from typing import Any

try:
    from .store import PonderForgeStore
except ImportError:
    from store import PonderForgeStore

JsonDict = dict[str, Any]


def _edge_relation_for_evidence(item: JsonDict) -> str:
    return "refutes" if item.get("counterevidence") else "supports"


def ingest_report(store: PonderForgeStore, payload: JsonDict) -> JsonDict:
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
