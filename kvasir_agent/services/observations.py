"""Bounded advisory progress/cost reads; never determine process completion."""
from datetime import datetime, timezone
import math

from .evidence_contracts import EvidenceError, read_json, validate_document
from .research_state import within


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timezone required")
    return parsed


def observations(state, record):
    output = {}
    root = state.path(f"runs/{record['run_id']}")
    spec = record.get("spec", {})
    for kind in ("progress", "cost"):
        relative = spec.get(kind + "_path")
        result = {"status": "unknown"}
        if relative:
            try:
                path = within(root, relative, exists=True)
                data = validate_document(read_json(path, limit=65536), kind)
                if data["run_id"] != record["run_id"]:
                    raise EvidenceError("observation_identity_mismatch", "Observation belongs to another run.")
                result = {"status": "reported", "path": str(path), "basis": "program_declared"}
                if kind == "progress":
                    age = (datetime.now(timezone.utc) - timestamp(data["updated_at"])).total_seconds()
                    if age < 0:
                        raise ValueError("Future observation")
                    if data.get("total") is not None and data.get("step", 0) > data["total"]:
                        raise ValueError("Step exceeds total")
                    for field in ("heartbeat_at", "last_progress_at"):
                        if field in data:
                            timestamp(data[field])
                    result.update(status="stale" if age > 300 else "reported", age_seconds=round(age, 1),
                                  phase=data["phase"][:120], liveness="not_assessed")
                    for field in ("step", "total", "heartbeat_at", "last_progress_at"):
                        if field in data:
                            result[field] = data[field]
                    if "versions" in data:
                        result["versions"] = {key: value[:120] for key, value in data["versions"].items()}
                else:
                    entries = data["entries"]
                    result.update(entries=[{**e, "unit": e["unit"][:80]} for e in entries[:5]],
                                  omitted_entries=max(0, len(entries) - 5))
            except (EvidenceError, OSError, ValueError, TypeError, KeyError):
                result = {"status": "unavailable_or_invalid", "path": relative[:160]}
        if kind == "cost":
            wall = record.get("elapsed_seconds")
            if isinstance(wall, (int, float)) and not isinstance(wall, bool) and math.isfinite(wall) and wall >= 0:
                result["managed_wall_seconds"] = wall
                result["managed_wall_basis"] = "observed"
            result["unreported_resources"] = "unknown"
        output[kind] = result
    return output
