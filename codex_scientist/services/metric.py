from __future__ import annotations

import math
from typing import Any


def _numeric_value(value: Any) -> dict[str, Any]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Metric value is not numeric", "error_type": "metric_invalid", "recoverable": True}
    if not math.isfinite(numeric):
        return {"ok": False, "error": "Metric value is not finite", "error_type": "metric_not_finite", "recoverable": False}
    return {"ok": True, "value": numeric}


def extract_metric_value(payload: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Extract a numeric metric value from a trusted metrics payload.

    Supported parser kinds are intentionally limited to simple data lookups.
    Log regex parsing belongs to FeedbackIngestService and never runs here.
    """

    if not isinstance(payload, dict) or not isinstance(contract, dict):
        return {"ok": False, "error": "Metric payload and contract must be objects", "error_type": "metric_parser_invalid", "recoverable": True}
    parser = str(contract.get("parser") or contract.get("kind") or "").strip()
    if parser == "json_path":
        path = str(contract.get("path") or "").strip()
        if not path or any(part == "" for part in path.split(".")):
            return {"ok": False, "error": "json_path parser requires a dotted path", "error_type": "metric_parser_invalid", "recoverable": True}
        current: Any = payload
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return {"ok": False, "error": f"Metric path not found: {path}", "error_type": "metric_missing", "recoverable": True}
            current = current[part]
        return _numeric_value(current)
    if parser == "flat_key":
        key = str(contract.get("key") or contract.get("path") or "").strip()
        if not key:
            return {"ok": False, "error": "flat_key parser requires key", "error_type": "metric_parser_invalid", "recoverable": True}
        if key not in payload:
            return {"ok": False, "error": f"Metric key not found: {key}", "error_type": "metric_missing", "recoverable": True}
        return _numeric_value(payload[key])
    return {"ok": False, "error": f"Unsupported metric parser: {parser}", "error_type": "metric_parser_invalid", "recoverable": True}


def validate_metric_result(contract: dict[str, Any], *, value: float, artifacts: list[str]) -> dict[str, Any]:
    validation = contract.get("validation") if isinstance(contract.get("validation"), dict) else {}
    numeric = float(value)
    if validation.get("finite", True) and not math.isfinite(numeric):
        return {"ok": False, "error": "Metric value is not finite", "error_type": "metric_not_finite", "recoverable": False}

    bounds = validation.get("range") or [None, None]
    lower = bounds[0] if len(bounds) > 0 else None
    upper = bounds[1] if len(bounds) > 1 else None
    if lower is not None and numeric < float(lower):
        return {"ok": False, "error": "Metric value is below allowed range", "error_type": "metric_out_of_range", "recoverable": False}
    if upper is not None and numeric > float(upper):
        return {"ok": False, "error": "Metric value is above allowed range", "error_type": "metric_out_of_range", "recoverable": False}

    artifact_set = set(artifacts)
    for required in validation.get("required_artifacts") or []:
        if required not in artifact_set:
            return {"ok": False, "error": f"Missing required metric artifact: {required}", "error_type": "missing_metric_artifact", "recoverable": True}
    return {"ok": True, "value": numeric}
