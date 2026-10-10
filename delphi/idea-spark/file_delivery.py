"""Prepare worker output paths and register files after native worker completion."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

try:
    from .schemas import ARTIFACT_TYPES
    from .store import IdeaSparkStore, canonical_json
    from .tools import idea_spark_artifact_create
except ImportError:
    from schemas import ARTIFACT_TYPES
    from store import IdeaSparkStore, canonical_json
    from tools import idea_spark_artifact_create


def prepare_file(args) -> dict:
    for field in ("room_id", "agent_id", "title"):
        if not getattr(args, field).strip():
            raise ValueError(f"{field} must be nonempty")
    store = IdeaSparkStore()
    store.initialize()
    if args.artifact_type not in ARTIFACT_TYPES:
        raise ValueError("invalid artifact type")
    with store.connect() as conn:
        if not conn.execute("select 1 from rooms where room_id = ?", (args.room_id,)).fetchone():
            raise ValueError("unknown room_id")
    artifact_id = "artifact_" + uuid.uuid4().hex
    directory = store.db_path.resolve().parent / "deliveries" / artifact_id
    directory.mkdir(parents=True)
    metadata = {key: getattr(args, key) for key in ("role", "phase", "round_id") if getattr(args, key)}
    receipt = {
        "version": 1,
        "db_path": str(store.db_path.resolve()),
        "artifact_id": artifact_id,
        "room_id": args.room_id,
        "artifact_type": args.artifact_type,
        "producer_agent": args.agent_id,
        "title": args.title,
        "file_path": str(directory / "result.md"),
        "content": {"summary": args.summary} if args.summary else {},
        "metadata": metadata,
    }
    receipt_path = directory / "receipt.json"
    receipt_path.write_text(canonical_json(receipt) + "\n", encoding="utf-8")
    return {"success": True, "receipt_path": str(receipt_path), **receipt}


def collect_files(paths: list[str]) -> dict:
    """Each receipt is independent so one missing worker cannot lose other results."""
    results = []
    db_path = str(IdeaSparkStore().db_path.resolve())
    for name in paths:
        result = {"receipt_path": str(Path(name).resolve())}
        try:
            receipt = json.loads(Path(name).read_text(encoding="utf-8"))
            if not isinstance(receipt, dict) or receipt.get("version") != 1:
                raise ValueError("unsupported delivery receipt")
            if receipt.get("db_path") != db_path:
                raise ValueError("receipt belongs to a different Delphi project")
            for field in ("artifact_id", "room_id", "artifact_type", "producer_agent", "file_path"):
                if not isinstance(receipt.get(field), str) or not receipt[field].strip():
                    raise ValueError(f"receipt missing {field}")
            result.update(json.loads(idea_spark_artifact_create(receipt)))
        except Exception as exc:
            result.update(success=False, error=str(exc))
        results.append(result)
    return {"success": all(item["success"] for item in results), "deliveries": results}
