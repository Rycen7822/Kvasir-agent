from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .graph import build_graph
    from .store import PonderForgeStore, json_dumps
except ImportError:
    from graph import build_graph
    from store import PonderForgeStore, json_dumps

JsonDict = dict[str, Any]


def _links_by_statement(store: PonderForgeStore) -> dict[str, list[str]]:
    links: dict[str, list[str]] = {}
    for row in store.list_rows("statement_assertion_links"):
        links.setdefault(row["statement_id"], []).append(row["assertion_id"])
    return links


def _accepted_assertions(store: PonderForgeStore, run_id: str) -> dict[str, JsonDict]:
    return {
        row["assertion_id"]: row
        for row in store.list_rows("assertions", run_id)
        if row.get("status") == "accepted"
    }


def _group_by(rows: list[JsonDict], key: str) -> dict[str, list[JsonDict]]:
    grouped: dict[str, list[JsonDict]] = {}
    for row in rows:
        value = row.get(key)
        if value:
            grouped.setdefault(str(value), []).append(row)
    return grouped


def _clip(value: object, limit: int = 240) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _render_trace(
    assertion: JsonDict,
    evidence_by_assertion: dict[str, list[JsonDict]],
    artifacts_by_report: dict[str, list[JsonDict]],
    verdicts_by_assertion: dict[str, list[JsonDict]],
) -> list[str]:
    lines: list[str] = []
    assertion_id = str(assertion["assertion_id"])
    evidence_items = evidence_by_assertion.get(assertion_id, [])
    if evidence_items:
        lines.append("  - Evidence trace:")
        for evidence in evidence_items[:6]:
            source = _clip(evidence.get("source_ref")) or "unknown source"
            observation = _clip(evidence.get("quote_or_observation"))
            suffix = f" — {observation}" if observation else ""
            lines.append(f"    - `{evidence.get('evidence_type')}`: {source}{suffix}")

    report_id = assertion.get("report_id")
    artifacts = artifacts_by_report.get(str(report_id), []) if report_id else []
    if artifacts:
        lines.append("  - Artifact trace:")
        for artifact in artifacts[:6]:
            path = _clip(artifact.get("path")) or "unknown path"
            summary = _clip(artifact.get("summary"))
            suffix = f" — {summary}" if summary else ""
            lines.append(f"    - `{artifact.get('artifact_type')}`: {path}{suffix}")

    verdicts = verdicts_by_assertion.get(assertion_id, [])
    if verdicts:
        lines.append("  - Verifier verdicts:")
        for verdict in verdicts[:6]:
            confidence = verdict.get("confidence")
            confidence_text = f", confidence={confidence}" if confidence is not None else ""
            rationale = _clip(verdict.get("rationale"))
            suffix = f" — {rationale}" if rationale else ""
            lines.append(f"    - `{verdict.get('verdict')}` by {verdict.get('reviewer_role')}{confidence_text}{suffix}")
    return lines


def _write_json(path: Path, payload: JsonDict) -> None:
    path.write_text(json_dumps(payload) + "\n", encoding="utf-8")


def render_final_report(store: PonderForgeStore, run_id: str) -> JsonDict:
    statements = store.list_rows("final_statements", run_id)
    accepted = _accepted_assertions(store, run_id)
    links = _links_by_statement(store)
    gaps: list[JsonDict] = []

    for statement in statements:
        if statement.get("status") in {"limitation", "open_issue"}:
            continue
        linked = [assertion_id for assertion_id in links.get(statement["statement_id"], []) if assertion_id in accepted]
        if not linked:
            gaps.append(
                {
                    "statement_id": statement["statement_id"],
                    "reason": "final statement has no accepted assertion link",
                }
            )

    if gaps:
        return {"status": "blocked", "run_id": run_id, "gaps": gaps}

    if not statements:
        for assertion in accepted.values():
            statement = store.create_final_statement(
                run_id,
                section="Findings",
                text=assertion["text"],
                status="material",
            )
            store.link_final_statement(statement["statement_id"], assertion["assertion_id"], relation="rendered_as")
            links.setdefault(statement["statement_id"], []).append(assertion["assertion_id"])
            statements.append(statement)

    evidence_by_assertion = _group_by(store.list_rows("evidence_items", run_id), "assertion_id")
    artifacts_by_report = _group_by(store.list_rows("artifacts", run_id), "report_id")
    verdicts_by_assertion = _group_by(store.list_rows("verification_verdicts", run_id), "target_id")

    sections: dict[str, list[tuple[str, list[str]]]] = {}
    for statement in statements:
        linked = [assertion_id for assertion_id in links.get(statement["statement_id"], []) if assertion_id in accepted]
        sections.setdefault(str(statement["section"]), []).append((str(statement["text"]), linked))

    lines = ["# Ponder-Forge Final Report", ""]
    for section, items in sections.items():
        lines.extend([f"## {section}", ""])
        for item, linked_assertion_ids in items:
            lines.append(f"- {item}")
            for assertion_id in linked_assertion_ids:
                lines.extend(_render_trace(accepted[assertion_id], evidence_by_assertion, artifacts_by_report, verdicts_by_assertion))
        lines.append("")
    final_md = "\n".join(lines).rstrip() + "\n"

    run_dir = store.run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    final_path = run_dir / "final.md"
    graph_path = run_dir / "graph.json"
    verdicts_path = run_dir / "verdicts.json"
    pool_status_path = run_dir / "pool_status.json"
    final_path.write_text(final_md, encoding="utf-8")
    _write_json(graph_path, build_graph(store, run_id))
    _write_json(verdicts_path, {"verdicts": store.list_rows("verification_verdicts", run_id)})
    _write_json(pool_status_path, {"run_id": run_id, "status": "final"})
    store.update_final_report(run_id, final_md)

    return {
        "status": "final",
        "run_id": run_id,
        "final_report_markdown": final_md,
        "artifact_paths": {
            "final_md": str(final_path),
            "graph_json": str(graph_path),
            "verdicts_json": str(verdicts_path),
            "pool_status_json": str(pool_status_path),
        },
    }
