from __future__ import annotations

import math


def test_metric_contract_accepts_finite_in_range_value_with_required_artifacts():
    from codex_scientist.services.metric import validate_metric_result

    contract = {
        "id": "primary",
        "direction": "maximize",
        "validation": {"finite": True, "range": [0.0, 1.0], "required_artifacts": ["metrics.json"]},
    }

    result = validate_metric_result(contract, value=0.75, artifacts=["metrics.json"])
    assert result == {"ok": True, "value": 0.75}


def test_metric_contract_rejects_nan_out_of_range_and_missing_artifacts():
    from codex_scientist.services.metric import validate_metric_result

    contract = {
        "id": "primary",
        "direction": "minimize",
        "validation": {"finite": True, "range": [0.0, 1.0], "required_artifacts": ["metrics.json"]},
    }

    nan_result = validate_metric_result(contract, value=math.nan, artifacts=["metrics.json"])
    assert nan_result["ok"] is False
    assert nan_result["error_type"] == "metric_not_finite"

    range_result = validate_metric_result(contract, value=2.0, artifacts=["metrics.json"])
    assert range_result["ok"] is False
    assert range_result["error_type"] == "metric_out_of_range"

    artifact_result = validate_metric_result(contract, value=0.5, artifacts=[])
    assert artifact_result["ok"] is False
    assert artifact_result["error_type"] == "missing_metric_artifact"
