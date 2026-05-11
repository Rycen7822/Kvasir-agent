from __future__ import annotations

import math
from typing import Any


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
