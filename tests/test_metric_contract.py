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


def test_metric_contract_extracts_json_path_and_flat_key_values():
    from codex_scientist.services.metric import extract_metric_value

    payload = {"metrics": {"eval": {"mean_reward": 0.75}}, "acc": 0.9}

    json_result = extract_metric_value(payload, {"parser": "json_path", "path": "metrics.eval.mean_reward"})
    assert json_result == {"ok": True, "value": 0.75}

    flat_result = extract_metric_value(payload, {"parser": "flat_key", "key": "acc"})
    assert flat_result == {"ok": True, "value": 0.9}


def test_metric_contract_rejects_missing_or_unsupported_parser():
    from codex_scientist.services.metric import extract_metric_value

    missing = extract_metric_value({"metrics": {}}, {"parser": "json_path", "path": "metrics.eval.mean_reward"})
    assert missing["ok"] is False
    assert missing["error_type"] == "metric_missing"

    unsupported = extract_metric_value({"acc": 1.0}, {"parser": "regex_log", "path": "acc=(.*)"})
    assert unsupported["ok"] is False
    assert unsupported["error_type"] == "metric_parser_invalid"
