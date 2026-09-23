from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .skill_index import search_skill_cards


def _load_cases(cases_path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in cases_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            loaded = json.loads(line)
            if isinstance(loaded, dict):
                cases.append(loaded)
    return cases


def evaluate_cases(*, skills_root: Path, cases_path: Path) -> dict[str, Any]:
    cases = _load_cases(cases_path)
    top1_hits = 0
    hit_at_k = 0
    forbidden_count = 0
    latencies: list[float] = []
    misses: list[dict[str, Any]] = []
    missing_expected_candidates: list[dict[str, Any]] = []
    forbidden_candidates: list[dict[str, Any]] = []
    average_precisions: list[float] = []
    judged_precisions: list[float] = []
    for case in cases:
        limit = int(case.get("k") or 3)
        payload = {
            "raw_user_request": case.get("raw_user_request", ""),
            "description_query": case.get("description_query", ""),
            "workflow_query": case.get("workflow_query", ""),
            "limit": limit,
            "max_chars": 4000,
        }
        start = perf_counter()
        result = search_skill_cards(payload, skills_root=skills_root)
        latencies.append((perf_counter() - start) * 1000)
        candidates = result.get("candidates") or []
        ids = [candidate.get("skill_id") for candidate in candidates[:limit]]
        expected_top = case.get("expected_top")
        expected_in_top_k = set(case.get("expected_in_top_k") or [])
        forbidden = set(case.get("forbidden") or [])
        if ids and ids[0] == expected_top:
            top1_hits += 1
        else:
            misses.append({"id": case.get("id"), "expected_top": expected_top, "actual": ids[:1]})
        if expected_in_top_k.intersection(ids):
            hit_at_k += 1
        else:
            missing_expected_candidates.append({"id": case.get("id"), "expected": sorted(expected_in_top_k), "actual": ids})
        hits = 0
        precision_sum = 0.0
        for rank, skill_id in enumerate(ids, start=1):
            if skill_id in expected_in_top_k:
                hits += 1
                precision_sum += hits / rank
        average_precisions.append(precision_sum / max(1, len(expected_in_top_k)))
        judged_precisions.append(hits / max(1, len(ids)))
        forbidden_hits = forbidden.intersection(ids)
        if forbidden_hits:
            forbidden_candidates.append({"id": case.get("id"), "forbidden": sorted(forbidden_hits), "actual": ids})
        forbidden_count += len(forbidden_hits)
    case_count = len(cases)
    return {
        "case_count": case_count,
        "top1_accuracy": (top1_hits / case_count) if case_count else 0.0,
        "hit_rate_at_k": (hit_at_k / case_count) if case_count else 0.0,
        "forbidden_count": forbidden_count,
        "average_latency_ms": (sum(latencies) / len(latencies)) if latencies else 0.0,
        "mean_average_precision_at_k": (sum(average_precisions) / len(average_precisions)) if average_precisions else 0.0,
        "judged_precision_at_k": (sum(judged_precisions) / len(judged_precisions)) if judged_precisions else 0.0,
        "missing_expected_candidates": missing_expected_candidates,
        "forbidden_candidates": forbidden_candidates,
        "top1_misses": misses,
    }
