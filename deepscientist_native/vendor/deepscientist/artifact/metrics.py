from __future__ import annotations

from collections import OrderedDict
from typing import Any


class MetricContractValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "metric_contract_validation_failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}

    def as_payload(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error_code": self.error_code,
            "message": str(self),
            **self.details,
        }


def as_metric_id(value: object, *, fallback: str | None = None) -> str:
    text = str(value or "").strip()
    if text:
        return text
    if fallback:
        return fallback
    raise ValueError("Metric id is required.")


def to_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def infer_metric_direction(metric_id: str) -> str:
    normalized = metric_id.strip().lower()
    if any(token in normalized for token in ("loss", "error", "wer", "cer", "perplex", "latency", "time")):
        return "minimize"
    return "maximize"


def normalize_metric_direction(value: object, *, metric_id: str | None = None) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"maximize", "max", "higher", "higher_better", "more_is_better", "greater_is_better"}:
        return "maximize"
    if text in {"minimize", "min", "lower", "lower_better", "less_is_better", "smaller_is_better"}:
        return "minimize"
    if metric_id:
        return infer_metric_direction(metric_id)
    return "maximize"


def normalize_metrics_summary(summary: object) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, value in summary.items():
        metric_id = str(key or "").strip()
        if not metric_id:
            continue
        normalized[metric_id] = value
    return normalized


def flatten_metric_leaf_map(summary: object, *, separator: str = ".") -> dict[str, Any]:
    flattened: OrderedDict[str, Any] = OrderedDict()

    def visit(value: object, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = str(key or "").strip()
                if not normalized_key:
                    continue
                visit(child, (*path, normalized_key))
            return
        if path:
            flattened[separator.join(path)] = value

    if isinstance(summary, dict):
        for key, value in summary.items():
            normalized_key = str(key or "").strip()
            if not normalized_key:
                continue
            visit(value, (normalized_key,))
    return dict(flattened)


def _resolve_origin_path_value(summary: object, origin_path: object) -> Any:
    if not isinstance(summary, dict):
        return None
    normalized_path = str(origin_path or "").strip().replace("/", ".")
    if not normalized_path:
        return None
    current: Any = summary
    for part in normalized_path.split("."):
        normalized_part = str(part or "").strip()
        if not normalized_part:
            continue
        if not isinstance(current, dict) or normalized_part not in current:
            return None
        current = current[normalized_part]
    return current


def _metric_explanation_fields(metric: dict[str, Any]) -> dict[str, str | None]:
    description = str(metric.get("description") or metric.get("explanation") or "").strip() or None
    derivation = str(metric.get("derivation") or metric.get("how_derived") or "").strip() or None
    source_ref = str(metric.get("source_ref") or metric.get("source") or "").strip() or None
    origin_path = str(metric.get("origin_path") or metric.get("source_path") or "").strip() or None
    return {
        "description": description,
        "derivation": derivation,
        "source_ref": source_ref,
        "origin_path": origin_path,
    }


def resolve_metric_value_from_summary(
    metric_id: str,
    *,
    metrics_summary: object = None,
    primary_metric: object = None,
    origin_path: object = None,
) -> float | None:
    normalized_metric_id = str(metric_id or "").strip()
    if not normalized_metric_id:
        return None
    summary = normalize_metrics_summary(metrics_summary)
    direct_value = summary.get(normalized_metric_id)
    direct_number = to_number(direct_value)
    if direct_number is not None:
        return direct_number
    origin_value = _resolve_origin_path_value(metrics_summary, origin_path)
    origin_number = to_number(origin_value)
    if origin_number is not None:
        return origin_number
    if isinstance(primary_metric, dict):
        primary_metric_id = str(
            primary_metric.get("metric_id") or primary_metric.get("name") or primary_metric.get("id") or ""
        ).strip()
        if primary_metric_id == normalized_metric_id:
            primary_number = to_number(primary_metric.get("value"))
            if primary_number is not None:
                return primary_number
    elif isinstance(primary_metric, str) and primary_metric.strip() == normalized_metric_id:
        return None
    return None


def canonicalize_baseline_submission(
    *,
    metric_contract: object,
    metrics_summary: object = None,
    primary_metric: object = None,
) -> dict[str, Any]:
    contract_payload = metric_contract if isinstance(metric_contract, dict) else {}
    explicit_metrics = contract_payload.get("metrics") if isinstance(contract_payload.get("metrics"), list) else []
    normalized_contract = normalize_metric_contract(
        contract_payload,
        metrics_summary=None,
        primary_metric=primary_metric,
    )
    canonical_metrics: OrderedDict[str, float] = OrderedDict()
    metric_details: list[dict[str, Any]] = []
    unresolved_metric_ids: list[str] = []

    if explicit_metrics:
        for metric in normalized_contract.get("metrics", []):
            if not isinstance(metric, dict):
                continue
            metric_id = str(metric.get("metric_id") or "").strip()
            if not metric_id:
                continue
            explanation = _metric_explanation_fields(metric)
            value = resolve_metric_value_from_summary(
                metric_id,
                metrics_summary=metrics_summary,
                primary_metric=primary_metric,
                origin_path=explanation.get("origin_path"),
            )
            required = bool(metric.get("required", True))
            detail = {
                **metric,
                "metric_id": metric_id,
                "required": required,
                **explanation,
            }
            if value is None:
                if required:
                    unresolved_metric_ids.append(metric_id)
                detail["value"] = None
            else:
                canonical_metrics[metric_id] = value
                detail["value"] = value
            metric_details.append(detail)
    else:
        for metric_id, value in extract_numeric_metric_map(metrics_summary=metrics_summary).items():
            canonical_metrics[metric_id] = value
            metric_details.append(
                {
                    "metric_id": metric_id,
                    "required": True,
                    "description": None,
                    "derivation": None,
                    "source_ref": None,
                    "origin_path": None,
                    "value": value,
                }
            )

    return {
        "metric_contract": normalized_contract,
        "metrics_summary": dict(canonical_metrics),
        "metric_details": metric_details,
        "unresolved_metric_ids": unresolved_metric_ids,
        "source_leaf_map": flatten_metric_leaf_map(metrics_summary),
    }


def validate_baseline_metric_contract_submission(
    *,
    metric_contract: object,
    metrics_summary: object = None,
    primary_metric: object = None,
) -> dict[str, Any]:
    canonical = canonicalize_baseline_submission(
        metric_contract=metric_contract,
        metrics_summary=metrics_summary,
        primary_metric=primary_metric,
    )
    normalized_contract = canonical["metric_contract"]
    metric_details = canonical["metric_details"]
    canonical_metrics = canonical["metrics_summary"]
    explicit_metrics = normalized_contract.get("metrics") if isinstance(normalized_contract.get("metrics"), list) else []
    if not explicit_metrics:
        raise MetricContractValidationError(
            "Baseline metric contract must define explicit metric entries for every canonical metric.",
            error_code="baseline_metric_contract_missing_entries",
            details={
                "validation_stage": "baseline",
                "baseline_metric_ids": [],
                "baseline_metric_details": metric_details,
                "source_metric_paths": sorted(canonical["source_leaf_map"].keys()),
            },
        )

    missing_explanations: list[dict[str, Any]] = []
    for detail in metric_details:
        if not isinstance(detail, dict):
            continue
        missing_fields: list[str] = []
        if not str(detail.get("description") or "").strip():
            missing_fields.append("description")
        if not (str(detail.get("derivation") or "").strip() or str(detail.get("origin_path") or "").strip()):
            missing_fields.append("derivation_or_origin_path")
        if not str(detail.get("source_ref") or "").strip():
            missing_fields.append("source_ref")
        if missing_fields:
            missing_explanations.append(
                {
                    "metric_id": detail.get("metric_id"),
                    "missing_fields": missing_fields,
                    "detail": detail,
                }
            )

    if canonical["unresolved_metric_ids"]:
        raise MetricContractValidationError(
            "Baseline metric contract is missing canonical values for one or more required metrics.",
            error_code="baseline_metric_values_missing",
            details={
                "validation_stage": "baseline",
                "missing_metric_ids": canonical["unresolved_metric_ids"],
                "baseline_metric_ids": list(canonical_metrics.keys()),
                "baseline_metric_details": metric_details,
                "source_metric_paths": sorted(canonical["source_leaf_map"].keys()),
            },
        )

    if missing_explanations:
        raise MetricContractValidationError(
            "Baseline metric contract must explain every canonical metric with description, derivation/origin path, and source reference.",
            error_code="baseline_metric_explanations_missing",
            details={
                "validation_stage": "baseline",
                "baseline_metric_ids": list(canonical_metrics.keys()),
                "baseline_metric_details": metric_details,
                "missing_explanations": missing_explanations,
                "source_metric_paths": sorted(canonical["source_leaf_map"].keys()),
            },
        )

    if not canonical_metrics:
        raise MetricContractValidationError(
            "Baseline metric contract did not yield any canonical numeric metrics.",
            error_code="baseline_metric_contract_empty",
            details={
                "validation_stage": "baseline",
                "baseline_metric_ids": [],
                "baseline_metric_details": metric_details,
                "source_metric_paths": sorted(canonical["source_leaf_map"].keys()),
            },
        )

    return canonical


def validate_main_experiment_against_baseline_contract(
    *,
    baseline_contract_payload: object,
    run_metric_contract: object = None,
    metric_rows: object = None,
    metrics_summary: object = None,
    dataset_scope: object = None,
) -> dict[str, Any]:
    baseline_payload = baseline_contract_payload if isinstance(baseline_contract_payload, dict) else {}
    if not baseline_payload:
        raise MetricContractValidationError(
            "Canonical baseline metric contract JSON is missing, so main-experiment metric validation cannot run.",
            error_code="baseline_metric_contract_json_missing",
            details={
                "validation_stage": "main_experiment",
                "baseline_metric_ids": [],
                "baseline_metric_details": [],
            },
        )
    baseline_metrics_summary = extract_numeric_metric_map(metrics_summary=baseline_payload.get("metrics_summary"))
    baseline_contract = normalize_metric_contract(
        baseline_payload.get("metric_contract"),
        metrics_summary=baseline_metrics_summary,
        primary_metric=baseline_payload.get("primary_metric"),
    )
    baseline_details = []
    required_metric_ids: list[str] = []
    baseline_meta_map = extract_metric_meta_map(
        metric_contract=baseline_contract,
        metrics_summary=baseline_metrics_summary,
    )
    for metric in baseline_contract.get("metrics", []):
        if not isinstance(metric, dict):
            continue
        metric_id = str(metric.get("metric_id") or "").strip()
        if not metric_id or metric_id not in baseline_metrics_summary:
            continue
        detail = {
            **metric,
            **_metric_explanation_fields(metric),
            "metric_id": metric_id,
            "baseline_value": baseline_metrics_summary.get(metric_id),
        }
        baseline_details.append(detail)
        if bool(metric.get("required", True)) and not bool(metric.get("supplementary", False)):
            required_metric_ids.append(metric_id)

    if not required_metric_ids:
        raise MetricContractValidationError(
            "Canonical baseline metric contract does not expose any required numeric metrics for comparison.",
            error_code="baseline_metric_contract_empty",
            details={
                "validation_stage": "main_experiment",
                "baseline_metric_ids": [],
                "baseline_metric_details": baseline_details,
            },
        )

    run_numeric_metrics = extract_numeric_metric_map(metric_rows=metric_rows, metrics_summary=metrics_summary)
    run_meta_map = extract_metric_meta_map(
        metric_contract=run_metric_contract,
        metric_rows=metric_rows,
        metrics_summary=metrics_summary,
    )
    missing_metric_ids = [metric_id for metric_id in required_metric_ids if metric_id not in run_numeric_metrics]
    extra_metric_ids = [metric_id for metric_id in run_numeric_metrics.keys() if metric_id not in required_metric_ids]
    direction_mismatches: list[dict[str, Any]] = []
    for metric_id in required_metric_ids:
        if metric_id not in run_numeric_metrics:
            continue
        baseline_direction = normalize_metric_direction(
            (baseline_meta_map.get(metric_id) or {}).get("direction"),
            metric_id=metric_id,
        )
        run_direction = normalize_metric_direction(
            (run_meta_map.get(metric_id) or {}).get("direction"),
            metric_id=metric_id,
        )
        if baseline_direction != run_direction:
            direction_mismatches.append(
                {
                    "metric_id": metric_id,
                    "expected_direction": baseline_direction,
                    "actual_direction": run_direction,
                }
            )

    expected_eval = (
        dict(baseline_contract.get("evaluation_protocol") or {})
        if isinstance(baseline_contract.get("evaluation_protocol"), dict)
        else {}
    )
    actual_eval = (
        dict((run_metric_contract or {}).get("evaluation_protocol") or {})
        if isinstance((run_metric_contract or {}).get("evaluation_protocol"), dict)
        else {}
    )
    expected_scope = str(
        expected_eval.get("scope_id")
        or expected_eval.get("dataset_scope")
        or dataset_scope
        or ""
    ).strip() or None
    actual_scopes = sorted(
        {
            str(row.get("scope_id") or row.get("scope") or dataset_scope or "").strip()
            for row in normalize_metric_rows(metric_rows, metrics_summary=metrics_summary)
            if isinstance(row, dict) and str(row.get("metric_id") or "").strip() in required_metric_ids
        }
        - {""}
    )
    scope_mismatch = bool(expected_scope and actual_scopes and any(scope != expected_scope for scope in actual_scopes))
    eval_protocol_mismatch: dict[str, Any] | None = None
    if expected_eval and actual_eval:
        expected_code_hashes = expected_eval.get("code_hashes") if isinstance(expected_eval.get("code_hashes"), dict) else {}
        actual_code_hashes = actual_eval.get("code_hashes") if isinstance(actual_eval.get("code_hashes"), dict) else {}
        expected_code_paths = expected_eval.get("code_paths") if isinstance(expected_eval.get("code_paths"), list) else []
        actual_code_paths = actual_eval.get("code_paths") if isinstance(actual_eval.get("code_paths"), list) else []
        if (
            str(expected_eval.get("scope_id") or expected_eval.get("dataset_scope") or "").strip()
            and str(expected_eval.get("scope_id") or expected_eval.get("dataset_scope") or "").strip()
            != str(actual_eval.get("scope_id") or actual_eval.get("dataset_scope") or "").strip()
        ) or (expected_code_hashes and actual_code_hashes and expected_code_hashes != actual_code_hashes) or (
            expected_code_paths and actual_code_paths and expected_code_paths != actual_code_paths
        ):
            eval_protocol_mismatch = {
                "expected": expected_eval,
                "actual": actual_eval,
            }

    if missing_metric_ids or direction_mismatches or scope_mismatch or eval_protocol_mismatch:
        details: dict[str, Any] = {
            "validation_stage": "main_experiment",
            "baseline_metric_ids": required_metric_ids,
            "baseline_metric_details": baseline_details,
            "missing_metric_ids": missing_metric_ids,
            "extra_metric_ids": extra_metric_ids,
        }
        if direction_mismatches:
            details["direction_mismatches"] = direction_mismatches
        if scope_mismatch:
            details["evaluation_protocol_mismatch"] = {
                "expected_scope_id": expected_scope,
                "actual_scope_ids": actual_scopes,
            }
        if eval_protocol_mismatch:
            details["evaluation_protocol_mismatch"] = eval_protocol_mismatch
        raise MetricContractValidationError(
            "Main experiment must cover every required baseline metric and stay aligned with the canonical evaluation contract.",
            error_code="main_experiment_metric_validation_failed",
            details=details,
        )

    return {
        "baseline_metric_ids": required_metric_ids,
        "baseline_metric_details": baseline_details,
        "extra_metric_ids": extra_metric_ids,
    }


def _normalize_metric_entry(metric: object, *, fallback_id: str | None = None) -> dict[str, Any]:
    if isinstance(metric, str):
        metric_id = as_metric_id(metric, fallback=fallback_id)
        return {
            "metric_id": metric_id,
            "label": metric_id,
            "direction": infer_metric_direction(metric_id),
            "unit": None,
            "decimals": None,
            "chart_group": "default",
        }
    if not isinstance(metric, dict):
        metric_id = as_metric_id(fallback_id)
        return {
            "metric_id": metric_id,
            "label": metric_id,
            "direction": infer_metric_direction(metric_id),
            "unit": None,
            "decimals": None,
            "chart_group": "default",
        }

    metric_id = as_metric_id(
        metric.get("metric_id") or metric.get("id") or metric.get("name") or fallback_id,
    )
    direction = normalize_metric_direction(metric.get("direction"), metric_id=metric_id)
    decimals_raw = metric.get("decimals")
    decimals = int(decimals_raw) if isinstance(decimals_raw, int) else None
    chart_group = str(metric.get("chart_group") or "default").strip() or "default"
    return {
        **metric,
        "metric_id": metric_id,
        "label": str(metric.get("label") or metric_id).strip() or metric_id,
        "direction": direction,
        "unit": str(metric.get("unit") or "").strip() or None,
        "decimals": decimals,
        "chart_group": chart_group,
    }


def normalize_metric_contract(
    contract: object,
    *,
    baseline_id: str | None = None,
    metrics_summary: object = None,
    metric_rows: object = None,
    primary_metric: object = None,
    baseline_variants: object = None,
) -> dict[str, Any]:
    contract_payload = contract if isinstance(contract, dict) else {}
    metrics_by_id: OrderedDict[str, dict[str, Any]] = OrderedDict()

    explicit_metrics = contract_payload.get("metrics") if isinstance(contract_payload.get("metrics"), list) else []
    for index, metric in enumerate(explicit_metrics):
        normalized = _normalize_metric_entry(metric, fallback_id=f"metric_{index + 1}")
        metrics_by_id[normalized["metric_id"]] = normalized

    summary_metrics = extract_numeric_metric_map(metric_rows=metric_rows, metrics_summary=metrics_summary)
    for metric_id in summary_metrics.keys():
        metrics_by_id.setdefault(metric_id, _normalize_metric_entry({}, fallback_id=metric_id))

    if isinstance(baseline_variants, list):
        for variant in baseline_variants:
            if not isinstance(variant, dict):
                continue
            for metric_id in extract_numeric_metric_map(metrics_summary=variant.get("metrics_summary")).keys():
                metrics_by_id.setdefault(metric_id, _normalize_metric_entry({}, fallback_id=metric_id))

    primary_metric_id = str(contract_payload.get("primary_metric_id") or "").strip()
    if not primary_metric_id:
        if isinstance(primary_metric, dict):
            primary_metric_id = str(
                primary_metric.get("metric_id") or primary_metric.get("name") or primary_metric.get("id") or ""
            ).strip()
        elif isinstance(primary_metric, str):
            primary_metric_id = primary_metric.strip()
    if not primary_metric_id and summary_metrics:
        primary_metric_id = next(iter(summary_metrics.keys()))
    if not primary_metric_id and metrics_by_id:
        primary_metric_id = next(iter(metrics_by_id.keys()))

    if primary_metric_id:
        metrics_by_id.setdefault(primary_metric_id, _normalize_metric_entry({}, fallback_id=primary_metric_id))

    preserved_top_level = {
        key: value
        for key, value in contract_payload.items()
        if key not in {"contract_id", "primary_metric_id", "metrics"}
    }
    return {
        **preserved_top_level,
        "contract_id": str(contract_payload.get("contract_id") or baseline_id or "default").strip() or "default",
        "primary_metric_id": primary_metric_id or None,
        "metrics": list(metrics_by_id.values()),
    }


def selected_baseline_metrics(entry: dict[str, Any] | None, selected_variant_id: str | None = None) -> dict[str, Any]:
    if not isinstance(entry, dict) or not entry:
        return {}

    def with_primary_metric(summary: dict[str, float], primary_metric: object) -> dict[str, float]:
        resolved = OrderedDict(summary)
        if isinstance(primary_metric, dict):
            metric_id = str(
                primary_metric.get("metric_id") or primary_metric.get("name") or primary_metric.get("id") or ""
            ).strip()
            value = to_number(primary_metric.get("value"))
            if metric_id and value is not None and metric_id not in resolved:
                resolved[metric_id] = value
        return dict(resolved)

    variants = entry.get("baseline_variants") if isinstance(entry.get("baseline_variants"), list) else []
    target_id = str(selected_variant_id or entry.get("default_variant_id") or "").strip()
    selected_variant = None
    if target_id:
        selected_variant = next(
            (item for item in variants if isinstance(item, dict) and str(item.get("variant_id") or "").strip() == target_id),
            None,
        )
    if selected_variant is None and variants:
        selected_variant = next((item for item in variants if isinstance(item, dict)), None)
    if isinstance(selected_variant, dict):
        summary = with_primary_metric(
            extract_numeric_metric_map(metrics_summary=selected_variant.get("metrics_summary")),
            selected_variant.get("primary_metric"),
        )
        if summary:
            return summary
    return with_primary_metric(
        extract_numeric_metric_map(metrics_summary=entry.get("metrics_summary")),
        entry.get("primary_metric"),
    )


def baseline_metric_lines(entry: dict[str, Any] | None, selected_variant_id: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(entry, dict) or not entry:
        return []

    def metrics_with_primary(summary: object, primary_metric: object) -> dict[str, float]:
        resolved = OrderedDict(extract_numeric_metric_map(metrics_summary=summary))
        if isinstance(primary_metric, dict):
            metric_id = str(
                primary_metric.get("metric_id") or primary_metric.get("name") or primary_metric.get("id") or ""
            ).strip()
            value = to_number(primary_metric.get("value"))
            if metric_id and value is not None and metric_id not in resolved:
                resolved[metric_id] = value
        return dict(resolved)

    baseline_id = str(entry.get("baseline_id") or entry.get("entry_id") or "").strip() or None
    selected_id = str(selected_variant_id or entry.get("default_variant_id") or "").strip() or None
    lines: list[dict[str, Any]] = []
    variants = entry.get("baseline_variants") if isinstance(entry.get("baseline_variants"), list) else []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        variant_id = str(variant.get("variant_id") or "").strip() or None
        variant_label = str(variant.get("label") or variant_id or "variant").strip() or "variant"
        metrics_summary = metrics_with_primary(variant.get("metrics_summary"), variant.get("primary_metric"))
        for metric_id, value in metrics_summary.items():
            lines.append(
                {
                    "metric_id": metric_id,
                    "label": f"{baseline_id or 'baseline'}:{variant_label}",
                    "baseline_id": baseline_id,
                    "variant_id": variant_id,
                    "selected": bool(selected_id and variant_id == selected_id),
                    "value": value,
                    "raw_value": value,
                }
            )
    if lines:
        return lines
    for metric_id, value in metrics_with_primary(entry.get("metrics_summary"), entry.get("primary_metric")).items():
        lines.append(
            {
                "metric_id": metric_id,
                "label": baseline_id or "baseline",
                "baseline_id": baseline_id,
                "variant_id": None,
                "selected": True,
                "value": value,
                "raw_value": value,
            }
        )
    return lines


def build_baseline_compare_payload(
    *,
    quest_id: str,
    baseline_entries: list[dict[str, Any]],
    active_baseline_id: str | None = None,
    active_variant_id: str | None = None,
) -> dict[str, Any]:
    series_map: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_meta_map: dict[str, dict[str, Any]] = {}
    deduped_entries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    ordered_baseline_entries: list[dict[str, Any]] = []
    primary_metric_id: str | None = None
    active_baseline_text = str(active_baseline_id or "").strip() or None
    active_variant_text = str(active_variant_id or "").strip() or None

    def entry_variant_groups(entry: dict[str, Any]) -> list[tuple[str | None, dict[str, Any] | None]]:
        variants = entry.get("baseline_variants") if isinstance(entry.get("baseline_variants"), list) else []
        if variants:
            groups: list[tuple[str | None, dict[str, Any] | None]] = []
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                groups.append((str(variant.get("variant_id") or "").strip() or None, variant))
            if groups:
                return groups
        return [(None, None)]

    def entry_key(entry: dict[str, Any], *, variant_id: str | None) -> str:
        baseline_id = str(entry.get("baseline_id") or entry.get("entry_id") or "").strip() or "baseline"
        variant_text = (
            str(variant_id or entry.get("default_variant_id") or "").strip()
            or "default"
        )
        return f"{baseline_id}::{variant_text}"

    def is_selected(entry: dict[str, Any], *, variant_id: str | None) -> bool:
        baseline_id = str(entry.get("baseline_id") or entry.get("entry_id") or "").strip() or None
        if not baseline_id or baseline_id != active_baseline_text:
            return False
        resolved_variant_id = str(variant_id or entry.get("default_variant_id") or "").strip() or None
        if active_variant_text:
            return resolved_variant_id == active_variant_text
        if resolved_variant_id:
            default_variant_id = str(entry.get("default_variant_id") or "").strip() or None
            return resolved_variant_id == (default_variant_id or resolved_variant_id)
        return True

    def ensure_series(metric_id: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        resolved_meta = meta or baseline_meta_map.get(metric_id) or _normalize_metric_entry({}, fallback_id=metric_id)
        if metric_id not in series_map:
            series_map[metric_id] = {
                "metric_id": metric_id,
                "label": resolved_meta.get("label") or metric_id,
                "direction": normalize_metric_direction(resolved_meta.get("direction"), metric_id=metric_id),
                "unit": resolved_meta.get("unit"),
                "decimals": resolved_meta.get("decimals"),
                "chart_group": resolved_meta.get("chart_group"),
                "values": [],
            }
        else:
            series_map[metric_id]["label"] = resolved_meta.get("label") or series_map[metric_id]["label"]
            series_map[metric_id]["direction"] = normalize_metric_direction(
                resolved_meta.get("direction") or series_map[metric_id]["direction"],
                metric_id=metric_id,
            )
            series_map[metric_id]["unit"] = resolved_meta.get("unit") or series_map[metric_id]["unit"]
            if resolved_meta.get("decimals") is not None:
                series_map[metric_id]["decimals"] = resolved_meta.get("decimals")
            series_map[metric_id]["chart_group"] = (
                resolved_meta.get("chart_group") or series_map[metric_id]["chart_group"]
            )
        return series_map[metric_id]

    for entry in baseline_entries:
        if not isinstance(entry, dict):
            continue
        baseline_id = str(entry.get("baseline_id") or entry.get("entry_id") or "").strip() or None
        if not baseline_id:
            continue
        for variant_id, _variant in entry_variant_groups(entry):
            deduped_entries[entry_key(entry, variant_id=variant_id)] = {
                **entry,
                "_compare_variant_id": variant_id,
            }

    for normalized_entry in deduped_entries.values():
        variant_id = str(normalized_entry.get("_compare_variant_id") or "").strip() or None
        contract = normalize_metric_contract(
            normalized_entry.get("metric_contract"),
            baseline_id=str(normalized_entry.get("baseline_id") or normalized_entry.get("entry_id") or ""),
            metrics_summary=selected_baseline_metrics(normalized_entry, variant_id),
            primary_metric=normalized_entry.get("primary_metric"),
            baseline_variants=normalized_entry.get("baseline_variants"),
        )
        if primary_metric_id is None:
            candidate_primary = str(contract.get("primary_metric_id") or "").strip() or None
            if candidate_primary:
                primary_metric_id = candidate_primary
        metric_meta = extract_metric_meta_map(
            metric_contract=normalized_entry.get("metric_contract"),
            metrics_summary=selected_baseline_metrics(normalized_entry, variant_id),
        )
        baseline_meta_map.update(metric_meta)
        compare_key = entry_key(normalized_entry, variant_id=variant_id)
        selected = is_selected(normalized_entry, variant_id=variant_id)
        ordered_baseline_entries.append(
            {
                "entry_key": compare_key,
                "baseline_id": str(normalized_entry.get("baseline_id") or normalized_entry.get("entry_id") or "").strip() or None,
                "variant_id": variant_id,
                "label": next(
                    (
                        str(item.get("label") or item.get("variant_id") or "").strip()
                        for item in (normalized_entry.get("baseline_variants") or [])
                        if isinstance(item, dict) and str(item.get("variant_id") or "").strip() == str(variant_id or "").strip()
                    ),
                    None,
                )
                or (variant_id or str(normalized_entry.get("baseline_id") or "").strip() or "baseline"),
                "baseline_kind": str(normalized_entry.get("baseline_kind") or "").strip() or None,
                "summary": str(normalized_entry.get("summary") or "").strip() or None,
                "selected": selected,
                "updated_at": normalized_entry.get("updated_at") or normalized_entry.get("created_at"),
                "metric_count": len(selected_baseline_metrics(normalized_entry, variant_id)),
            }
        )
        for line in baseline_metric_lines(normalized_entry, variant_id):
            metric_id = str(line.get("metric_id") or "").strip()
            if not metric_id:
                continue
            line_variant_id = str(line.get("variant_id") or "").strip() or None
            if line_variant_id != variant_id:
                if not (line_variant_id is None and variant_id is None):
                    continue
            ensure_series(metric_id, metric_meta.get(metric_id))
            series_map[metric_id]["values"].append(
                {
                    "entry_key": compare_key,
                    "label": line.get("label"),
                    "baseline_id": line.get("baseline_id"),
                    "variant_id": line.get("variant_id"),
                    "selected": selected,
                    "value": line.get("value"),
                    "raw_value": line.get("raw_value"),
                    "baseline_kind": str(normalized_entry.get("baseline_kind") or "").strip() or None,
                    "summary": str(normalized_entry.get("summary") or "").strip() or None,
                    "updated_at": normalized_entry.get("updated_at") or normalized_entry.get("created_at"),
                }
            )

    def sort_metric_values(series: dict[str, Any]) -> None:
        direction = normalize_metric_direction(series.get("direction"), metric_id=str(series.get("metric_id") or ""))

        def sort_key(item: dict[str, Any]) -> tuple[int, float, str]:
            value = to_number(item.get("value"))
            if value is None:
                metric_rank = float("inf")
            elif direction == "minimize":
                metric_rank = value
            else:
                metric_rank = -value
            return (0 if item.get("selected") else 1, metric_rank, str(item.get("label") or ""))

        series["values"].sort(key=sort_key)

    for series in series_map.values():
        sort_metric_values(series)

    ordered_baseline_entries.sort(
        key=lambda item: (
            0 if item.get("selected") else 1,
            str(item.get("updated_at") or ""),
            str(item.get("baseline_id") or ""),
            str(item.get("variant_id") or ""),
        )
    )

    return {
        "quest_id": quest_id,
        "primary_metric_id": primary_metric_id,
        "total_entries": len(ordered_baseline_entries),
        "baseline_ref": {
            "baseline_id": active_baseline_text,
            "variant_id": active_variant_text,
        }
        if active_baseline_text
        else None,
        "entries": ordered_baseline_entries,
        "series": [item for item in series_map.values() if item["values"]],
    }


def normalize_metric_rows(
    metric_rows: object,
    *,
    metrics_summary: object = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(metric_rows, list):
        for row in metric_rows:
            if not isinstance(row, dict):
                continue
            metric_id = str(row.get("metric_id") or row.get("name") or row.get("metric") or "").strip()
            if not metric_id:
                candidate_keys = [key for key in row.keys() if key not in {"split", "seed", "note", "notes"}]
                if len(candidate_keys) == 1:
                    metric_id = candidate_keys[0]
            if not metric_id:
                continue
            value = row.get("value", row.get(metric_id))
            rows.append(
                {
                    **row,
                    "metric_id": metric_id,
                    "value": value,
                    "numeric_value": to_number(value),
                }
            )
    if rows:
        return rows
    for metric_id, value in normalize_metrics_summary(metrics_summary).items():
        rows.append(
            {
                "metric_id": metric_id,
                "value": value,
                "numeric_value": to_number(value),
            }
        )
    return rows


def extract_numeric_metric_map(
    *,
    metric_rows: object = None,
    metrics_summary: object = None,
) -> dict[str, float]:
    metrics: OrderedDict[str, float] = OrderedDict()
    rows = normalize_metric_rows(metric_rows, metrics_summary=metrics_summary)
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric_id = str(row.get("metric_id") or "").strip()
        numeric_value = to_number(row.get("numeric_value", row.get("value")))
        if not metric_id or numeric_value is None:
            continue
        metrics[metric_id] = numeric_value
    for metric_id, value in normalize_metrics_summary(metrics_summary).items():
        numeric_value = to_number(value)
        if metric_id and numeric_value is not None and metric_id not in metrics:
            metrics[metric_id] = numeric_value
    return dict(metrics)


def extract_metric_raw_value_map(
    *,
    metric_rows: object = None,
    metrics_summary: object = None,
) -> dict[str, Any]:
    values: OrderedDict[str, Any] = OrderedDict()
    rows = normalize_metric_rows(metric_rows, metrics_summary=metrics_summary)
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric_id = str(row.get("metric_id") or "").strip()
        if not metric_id:
            continue
        values[metric_id] = row.get("value")
    for metric_id, value in normalize_metrics_summary(metrics_summary).items():
        if metric_id not in values:
            values[metric_id] = value
    return dict(values)


def extract_metric_meta_map(
    *,
    metric_contract: object = None,
    metric_rows: object = None,
    metrics_summary: object = None,
) -> dict[str, dict[str, Any]]:
    contract = normalize_metric_contract(
        metric_contract,
        metrics_summary=metrics_summary,
        metric_rows=metric_rows,
    )
    meta_map: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for item in contract.get("metrics", []):
        if not isinstance(item, dict):
            continue
        metric_id = str(item.get("metric_id") or "").strip()
        if not metric_id:
            continue
        meta_map[metric_id] = {
            **item,
            "metric_id": metric_id,
            "direction": normalize_metric_direction(item.get("direction"), metric_id=metric_id),
            "label": str(item.get("label") or metric_id).strip() or metric_id,
        }

    for row in normalize_metric_rows(metric_rows, metrics_summary=metrics_summary):
        if not isinstance(row, dict):
            continue
        metric_id = str(row.get("metric_id") or "").strip()
        if not metric_id:
            continue
        current = dict(meta_map.get(metric_id) or _normalize_metric_entry({}, fallback_id=metric_id))
        label = str(row.get("label") or row.get("name") or current.get("label") or metric_id).strip() or metric_id
        decimals = row.get("decimals") if isinstance(row.get("decimals"), int) else current.get("decimals")
        meta_map[metric_id] = {
            **current,
            "metric_id": metric_id,
            "label": label,
            "direction": normalize_metric_direction(row.get("direction") or current.get("direction"), metric_id=metric_id),
            "unit": str(row.get("unit") or current.get("unit") or "").strip() or None,
            "decimals": decimals,
            "chart_group": str(row.get("chart_group") or current.get("chart_group") or "default").strip() or "default",
        }

    for metric_id in extract_numeric_metric_map(metric_rows=metric_rows, metrics_summary=metrics_summary).keys():
        meta_map.setdefault(metric_id, _normalize_metric_entry({}, fallback_id=metric_id))
    return dict(meta_map)


def extract_metric_comparison_map(
    baseline_comparisons: object,
) -> dict[str, dict[str, Any]]:
    comparisons = baseline_comparisons if isinstance(baseline_comparisons, dict) else {}
    return {
        str(item.get("metric_id") or "").strip(): item
        for item in comparisons.get("items", [])
        if isinstance(item, dict) and item.get("metric_id")
    }


def extract_metric_delta_map(
    *,
    metric_rows: object = None,
    baseline_comparisons: object = None,
) -> dict[str, float]:
    delta_map: OrderedDict[str, float] = OrderedDict()
    for metric_id, item in extract_metric_comparison_map(baseline_comparisons).items():
        delta_value = to_number(item.get("delta"))
        if delta_value is not None:
            delta_map[metric_id] = delta_value
    for row in normalize_metric_rows(metric_rows):
        if not isinstance(row, dict):
            continue
        metric_id = str(row.get("metric_id") or "").strip()
        if not metric_id or metric_id in delta_map:
            continue
        delta_value = to_number(row.get("delta"))
        if delta_value is not None:
            delta_map[metric_id] = delta_value
    return dict(delta_map)


def resolve_primary_metric_id(
    *,
    metric_contract: object = None,
    metric_rows: object = None,
    metrics_summary: object = None,
    primary_metric: object = None,
    progress_eval: object = None,
    baseline_comparisons: object = None,
) -> str | None:
    numeric_metrics = extract_numeric_metric_map(metric_rows=metric_rows, metrics_summary=metrics_summary)
    if not numeric_metrics:
        return None

    contract = normalize_metric_contract(
        metric_contract,
        metrics_summary=metrics_summary,
        metric_rows=metric_rows,
        primary_metric=primary_metric,
    )
    candidates: list[str] = []
    for value in (
        (progress_eval or {}).get("primary_metric_id") if isinstance(progress_eval, dict) else None,
        (baseline_comparisons or {}).get("primary_metric_id") if isinstance(baseline_comparisons, dict) else None,
        contract.get("primary_metric_id"),
    ):
        candidate = str(value or "").strip()
        if candidate:
            candidates.append(candidate)
    if isinstance(primary_metric, dict):
        candidate = str(
            primary_metric.get("metric_id") or primary_metric.get("name") or primary_metric.get("id") or ""
        ).strip()
        if candidate:
            candidates.append(candidate)
    elif isinstance(primary_metric, str):
        candidate = primary_metric.strip()
        if candidate:
            candidates.append(candidate)
    for candidate in candidates:
        if candidate in numeric_metrics:
            return candidate
    return next(iter(numeric_metrics.keys()), None)


def extract_latest_metric(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not payload:
        return None
    numeric_metrics = extract_numeric_metric_map(
        metric_rows=payload.get("metric_rows"),
        metrics_summary=payload.get("metrics_summary"),
    )
    if not numeric_metrics:
        return None

    metric_id = resolve_primary_metric_id(
        metric_contract=payload.get("metric_contract"),
        metric_rows=payload.get("metric_rows"),
        metrics_summary=payload.get("metrics_summary"),
        primary_metric=payload.get("primary_metric"),
        progress_eval=payload.get("progress_eval"),
        baseline_comparisons=payload.get("baseline_comparisons"),
    )
    if not metric_id:
        return None
    metric_value = numeric_metrics.get(metric_id)
    if metric_value is None:
        return None

    meta_map = extract_metric_meta_map(
        metric_contract=payload.get("metric_contract"),
        metric_rows=payload.get("metric_rows"),
        metrics_summary=payload.get("metrics_summary"),
    )
    delta_map = extract_metric_delta_map(
        metric_rows=payload.get("metric_rows"),
        baseline_comparisons=payload.get("baseline_comparisons"),
    )
    meta = meta_map.get(metric_id) or {}
    result = {
        "key": metric_id,
        "value": metric_value,
    }
    if metric_id in delta_map:
        result["delta_vs_baseline"] = delta_map[metric_id]
    if meta.get("label"):
        result["label"] = meta["label"]
    if meta.get("direction"):
        result["direction"] = meta["direction"]
    if meta.get("unit"):
        result["unit"] = meta["unit"]
    if meta.get("decimals") is not None:
        result["decimals"] = meta["decimals"]
    return result


def compare_with_baseline(
    *,
    metrics_summary: object,
    metric_rows: object = None,
    metric_contract: object,
    baseline_metrics: object,
) -> dict[str, Any]:
    run_summary = extract_numeric_metric_map(metric_rows=metric_rows, metrics_summary=metrics_summary)
    baseline_summary = extract_numeric_metric_map(metrics_summary=baseline_metrics)
    contract = normalize_metric_contract(metric_contract, metrics_summary=run_summary, metric_rows=metric_rows)
    items: list[dict[str, Any]] = []
    metric_meta = extract_metric_meta_map(
        metric_contract=contract,
        metric_rows=metric_rows,
        metrics_summary=run_summary,
    )
    metric_ids = [
        metric_id
        for metric_id in metric_meta.keys()
        if metric_id in run_summary or metric_id in baseline_summary
    ]
    for metric_id in baseline_summary.keys():
        if metric_id not in metric_ids:
            metric_ids.append(metric_id)
    for metric_id in run_summary.keys():
        if metric_id not in metric_ids:
            metric_ids.append(metric_id)
    for metric_id in metric_ids:
        meta = metric_meta.get(metric_id) or _normalize_metric_entry({}, fallback_id=metric_id)
        run_value = run_summary.get(metric_id)
        baseline_value = baseline_summary.get(metric_id)
        run_number = to_number(run_value)
        baseline_number = to_number(baseline_value)
        delta = None
        relative_delta = None
        better = None
        if run_number is not None and baseline_number is not None:
            delta = run_number - baseline_number
            if baseline_number not in {0.0, -0.0}:
                relative_delta = delta / abs(baseline_number)
            direction = normalize_metric_direction(meta.get("direction"), metric_id=metric_id)
            if direction == "maximize":
                better = run_number > baseline_number
            else:
                better = run_number < baseline_number
        items.append(
            {
                "metric_id": metric_id,
                "label": meta.get("label") or metric_id,
                "direction": normalize_metric_direction(meta.get("direction"), metric_id=metric_id),
                "unit": meta.get("unit"),
                "decimals": meta.get("decimals"),
                "chart_group": meta.get("chart_group"),
                "run_value": run_value,
                "baseline_value": baseline_value,
                "run_numeric": run_number,
                "baseline_numeric": baseline_number,
                "delta": delta,
                "relative_delta": relative_delta,
                "better": better,
            }
        )

    primary_metric_id = resolve_primary_metric_id(
        metric_contract=contract,
        metrics_summary=run_summary,
    )
    primary_item = next((item for item in items if item["metric_id"] == primary_metric_id), None)
    if primary_item is None and items:
        primary_item = items[0]
        primary_metric_id = primary_item["metric_id"]

    improved = [item["metric_id"] for item in items if item.get("better") is True]
    regressed = [item["metric_id"] for item in items if item.get("better") is False]
    comparable = [item["metric_id"] for item in items if item.get("better") is not None]
    return {
        "primary_metric_id": primary_metric_id,
        "items": items,
        "summary": {
            "comparable_metric_ids": comparable,
            "improved_metric_ids": improved,
            "regressed_metric_ids": regressed,
        },
        "primary": primary_item,
    }


def compute_progress_eval(
    *,
    comparisons: dict[str, Any],
    previous_primary_best: float | None,
) -> dict[str, Any]:
    primary = comparisons.get("primary") if isinstance(comparisons, dict) else None
    if not isinstance(primary, dict):
        return {
            "primary_metric_id": None,
            "beats_baseline": None,
            "improved_over_previous_best": None,
            "breakthrough": False,
            "breakthrough_level": "none",
            "reason": "Primary metric is unavailable.",
        }

    direction = str(primary.get("direction") or infer_metric_direction(str(primary.get("metric_id") or ""))).strip()
    run_value = primary.get("run_numeric")
    baseline_value = primary.get("baseline_numeric")
    beats_baseline = primary.get("better")
    improved_over_previous = None
    delta_vs_previous = None
    if run_value is not None and previous_primary_best is not None:
        delta_vs_previous = run_value - previous_primary_best
        improved_over_previous = run_value > previous_primary_best if direction == "maximize" else run_value < previous_primary_best
    breakthrough = bool(improved_over_previous or (improved_over_previous is None and beats_baseline))
    if improved_over_previous:
        level = "major"
        reason = "Primary metric set a new best main-experiment result."
    elif beats_baseline:
        level = "minor"
        reason = "Primary metric beat the attached baseline."
    else:
        level = "none"
        reason = "No verified breakthrough over the active baseline or previous best."
    return {
        "primary_metric_id": primary.get("metric_id"),
        "direction": direction,
        "run_value": run_value,
        "baseline_value": baseline_value,
        "delta_vs_baseline": primary.get("delta"),
        "relative_delta_vs_baseline": primary.get("relative_delta"),
        "previous_best_value": previous_primary_best,
        "delta_vs_previous_best": delta_vs_previous,
        "beats_baseline": beats_baseline,
        "improved_over_previous_best": improved_over_previous,
        "breakthrough": breakthrough,
        "breakthrough_level": level,
        "reason": reason,
    }


def _record_sort_key(record: dict[str, Any]) -> str:
    return str(record.get("updated_at") or record.get("created_at") or "")


def _record_dedupe_key(record: dict[str, Any]) -> str:
    run_id = str(record.get("run_id") or "").strip()
    if run_id:
        return f"run:{run_id}"
    artifact_id = str(record.get("artifact_id") or "").strip()
    if artifact_id:
        return f"artifact:{artifact_id}"
    result_path = str(((record.get("paths") or {}) if isinstance(record.get("paths"), dict) else {}).get("result_json") or "").strip()
    if result_path:
        return f"path:{result_path}"
    branch_name = str(record.get("branch") or "").strip()
    return f"record:{branch_name}:{_record_sort_key(record)}"


def _record_richness(record: dict[str, Any]) -> tuple[int, int, int, int, str]:
    numeric_metrics = extract_numeric_metric_map(
        metric_rows=record.get("metric_rows"),
        metrics_summary=record.get("metrics_summary"),
    )
    comparisons = extract_metric_comparison_map(record.get("baseline_comparisons"))
    has_result_path = int(
        bool(((record.get("paths") or {}) if isinstance(record.get("paths"), dict) else {}).get("result_json"))
    )
    metric_meta = extract_metric_meta_map(
        metric_contract=record.get("metric_contract"),
        metric_rows=record.get("metric_rows"),
        metrics_summary=record.get("metrics_summary"),
    )
    return (
        len(numeric_metrics),
        len(comparisons),
        has_result_path,
        len(metric_meta),
        _record_sort_key(record),
    )


def dedupe_run_records(run_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for record in sorted(
        [item for item in run_records if isinstance(item, dict)],
        key=_record_sort_key,
    ):
        key = _record_dedupe_key(record)
        existing = deduped.get(key)
        if existing is None or _record_richness(record) >= _record_richness(existing):
            deduped[key] = record
    return sorted(deduped.values(), key=_record_sort_key)


def build_metrics_timeline(
    *,
    quest_id: str,
    run_records: list[dict[str, Any]],
    baseline_entry: dict[str, Any] | None = None,
    selected_variant_id: str | None = None,
) -> dict[str, Any]:
    ordered_runs = dedupe_run_records(run_records)
    baseline_metrics = selected_baseline_metrics(baseline_entry, selected_variant_id)
    contract = normalize_metric_contract(
        None,
        baseline_id=str((baseline_entry or {}).get("baseline_id") or ""),
        metrics_summary=baseline_metrics,
        primary_metric=(baseline_entry or {}).get("primary_metric"),
        baseline_variants=(baseline_entry or {}).get("baseline_variants"),
    )
    primary_metric_id = str(contract.get("primary_metric_id") or "").strip() or None
    for record in ordered_runs:
        candidate = resolve_primary_metric_id(
            metric_contract=record.get("metric_contract"),
            metric_rows=record.get("metric_rows"),
            metrics_summary=record.get("metrics_summary"),
            progress_eval=record.get("progress_eval"),
            baseline_comparisons=record.get("baseline_comparisons"),
        )
        if candidate:
            primary_metric_id = candidate
            break

    series_map: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_meta_map = extract_metric_meta_map(
        metric_contract=(baseline_entry or {}).get("metric_contract"),
        metrics_summary=baseline_metrics,
    )

    def ensure_series(metric_id: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        resolved_meta = meta or baseline_meta_map.get(metric_id) or _normalize_metric_entry({}, fallback_id=metric_id)
        if metric_id not in series_map:
            series_map[metric_id] = {
                "metric_id": metric_id,
                "label": resolved_meta.get("label") or metric_id,
                "direction": normalize_metric_direction(resolved_meta.get("direction"), metric_id=metric_id),
                "unit": resolved_meta.get("unit"),
                "decimals": resolved_meta.get("decimals"),
                "chart_group": resolved_meta.get("chart_group"),
                "baselines": [],
                "points": [],
            }
        else:
            series_map[metric_id]["label"] = resolved_meta.get("label") or series_map[metric_id]["label"]
            series_map[metric_id]["direction"] = normalize_metric_direction(
                resolved_meta.get("direction") or series_map[metric_id]["direction"],
                metric_id=metric_id,
            )
            series_map[metric_id]["unit"] = resolved_meta.get("unit") or series_map[metric_id]["unit"]
            if resolved_meta.get("decimals") is not None:
                series_map[metric_id]["decimals"] = resolved_meta.get("decimals")
            series_map[metric_id]["chart_group"] = (
                resolved_meta.get("chart_group") or series_map[metric_id]["chart_group"]
            )
        return series_map[metric_id]

    for metric in contract.get("metrics", []):
        metric_id = str(metric.get("metric_id") or "").strip()
        if not metric_id:
            continue
        ensure_series(metric_id, metric)

    for line in baseline_metric_lines(baseline_entry, selected_variant_id):
        metric_id = str(line.get("metric_id") or "").strip()
        if not metric_id:
            continue
        ensure_series(metric_id).setdefault("baselines", []).append(line)

    for index, record in enumerate(ordered_runs, start=1):
        numeric_metrics = extract_numeric_metric_map(
            metric_rows=record.get("metric_rows"),
            metrics_summary=record.get("metrics_summary"),
        )
        raw_values = extract_metric_raw_value_map(
            metric_rows=record.get("metric_rows"),
            metrics_summary=record.get("metrics_summary"),
        )
        progress = record.get("progress_eval") if isinstance(record.get("progress_eval"), dict) else {}
        comparison_by_id = extract_metric_comparison_map(record.get("baseline_comparisons"))
        delta_by_id = extract_metric_delta_map(
            metric_rows=record.get("metric_rows"),
            baseline_comparisons=record.get("baseline_comparisons"),
        )
        record_meta = extract_metric_meta_map(
            metric_contract=record.get("metric_contract"),
            metric_rows=record.get("metric_rows"),
            metrics_summary=record.get("metrics_summary"),
        )
        for metric_id, numeric_value in numeric_metrics.items():
            ensure_series(metric_id, record_meta.get(metric_id))
            comparison = comparison_by_id.get(metric_id, {})
            series_map[metric_id]["points"].append(
                {
                    "seq": index,
                    "run_id": record.get("run_id"),
                    "artifact_id": record.get("artifact_id"),
                    "created_at": record.get("updated_at") or record.get("created_at"),
                    "branch": record.get("branch"),
                    "idea_id": record.get("idea_id"),
                    "value": numeric_value,
                    "raw_value": raw_values.get(metric_id, numeric_value),
                    "delta_vs_baseline": delta_by_id.get(metric_id),
                    "relative_delta_vs_baseline": comparison.get("relative_delta"),
                    "breakthrough": bool(progress.get("breakthrough")),
                    "breakthrough_level": progress.get("breakthrough_level"),
                    "result_path": ((record.get("paths") or {}) if isinstance(record.get("paths"), dict) else {}).get("result_json"),
                }
            )

    series = [item for item in series_map.values() if item["points"] or item["baselines"]]
    return {
        "quest_id": quest_id,
        "primary_metric_id": primary_metric_id,
        "series": series,
        "total_runs": len(ordered_runs),
        "baseline_ref": {
            "baseline_id": (baseline_entry or {}).get("baseline_id"),
            "variant_id": selected_variant_id,
        }
        if baseline_entry
        else None,
    }
