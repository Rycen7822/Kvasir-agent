from __future__ import annotations

import json
from typing import Any

try:
    from .store import PonderForgeStore
except ImportError:
    from store import PonderForgeStore

JsonDict = dict[str, Any]

_NODE_TABLES = (
    ("reports", "report", "report_id"),
    ("assertions", "assertion", "assertion_id"),
    ("evidence_items", "evidence", "evidence_id"),
    ("artifacts", "artifact", "artifact_id"),
    ("verification_verdicts", "verdict", "verdict_id"),
    ("final_statements", "final_statement", "statement_id"),
)


def _decode_raw(row: JsonDict) -> JsonDict:
    raw = dict(row)
    for key in list(raw):
        if key.endswith("_json") and isinstance(raw[key], str):
            try:
                raw[key[:-5]] = json.loads(raw[key])
            except json.JSONDecodeError:
                raw[key[:-5]] = raw[key]
    return raw


def build_graph(store: PonderForgeStore, run_id: str) -> JsonDict:
    nodes: list[JsonDict] = []
    statement_ids: set[str] = set()
    for table, node_type, id_key in _NODE_TABLES:
        for row in store.list_rows(table, run_id):
            if table == "final_statements":
                statement_ids.add(str(row[id_key]))
            nodes.append({"id": row[id_key], "type": node_type, "raw": _decode_raw(row)})

    edges = store.list_rows("graph_edges", run_id)
    links = store.list_rows("statement_assertion_links")
    for link in links:
        if str(link["statement_id"]) not in statement_ids:
            continue
        edges.append(
            {
                "edge_id": f"{link['statement_id']}:{link['assertion_id']}",
                "run_id": run_id,
                "src_type": "final_statement",
                "src_id": link["statement_id"],
                "dst_type": "assertion",
                "dst_id": link["assertion_id"],
                "edge_type": link["relation"],
                "weight": 1.0,
                "raw_json": "{}",
            }
        )
    return {"run_id": run_id, "nodes": nodes, "edges": edges}
