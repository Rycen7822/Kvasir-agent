from __future__ import annotations

import json
from typing import Any


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text or text[:1] not in {"{", "["}:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return value


def _pick_string(*values: Any) -> str:
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text:
            return text
    return ""


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _unwrap_structured_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return value

    parsed = _parse_jsonish(value)
    if isinstance(parsed, list):
        if len(parsed) == 1 and isinstance(parsed[0], dict):
            block = parsed[0]
            for key in ("text", "content", "output"):
                nested = block.get(key)
                if nested is None or nested is value:
                    continue
                candidate = _unwrap_structured_value(nested, depth=depth + 1)
                if candidate is not None:
                    return candidate
        return parsed

    if not isinstance(parsed, dict):
        return parsed

    for key in (
        "structured_content",
        "structuredContent",
        "structured_result",
        "structuredResult",
        "result",
        "data",
        "payload",
    ):
        nested = parsed.get(key)
        if nested is None or nested is parsed:
            continue
        candidate = _unwrap_structured_value(nested, depth=depth + 1)
        if candidate is not None:
            return candidate

    content = parsed.get("content")
    if isinstance(content, list):
        text_blocks: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            nested = block.get("text") or block.get("content")
            if not isinstance(nested, str) or not nested.strip():
                continue
            candidate = _unwrap_structured_value(nested, depth=depth + 1)
            if candidate is not None:
                return candidate
            text_blocks.append(nested.strip())
        if text_blocks:
            return {"text": "\n\n".join(text_blocks)}

    return parsed


def _normalize_result_entry(value: Any) -> dict[str, Any] | None:
    parsed = _unwrap_structured_value(value)
    if isinstance(parsed, dict):
        record = parsed
        arxiv_id = _pick_string(record.get("arxiv_id"), record.get("paper_id"), record.get("id"))
        abs_url = _pick_string(
            record.get("abs_url"),
            f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
        )
        pdf_url = _pick_string(
            record.get("pdf_url"),
            f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else "",
        )
        url = _pick_string(record.get("link"), record.get("url"), record.get("href"), abs_url, pdf_url)
        title = _pick_string(record.get("title"), record.get("name"), record.get("headline"), record.get("label"), url)
        snippet = _pick_string(
            record.get("snippet"),
            record.get("abstract"),
            record.get("summary"),
            record.get("description"),
            record.get("text"),
            record.get("content"),
            record.get("message"),
        )
        source = _pick_string(
            record.get("source"),
            record.get("display_link"),
            record.get("domain"),
            record.get("host"),
            record.get("provider"),
        )
        normalized: dict[str, Any] = {}
        if title:
            normalized["title"] = title
        if snippet:
            normalized["snippet"] = snippet
        if url:
            normalized["link"] = url
            normalized["url"] = url
        if source:
            normalized["source"] = source
        if arxiv_id:
            normalized["arxiv_id"] = arxiv_id
        if abs_url:
            normalized["abs_url"] = abs_url
        if pdf_url:
            normalized["pdf_url"] = pdf_url
        return normalized or None

    if isinstance(parsed, str) and parsed.strip():
        return {"title": parsed.strip()}

    return None


def _extract_results(value: Any) -> list[dict[str, Any]]:
    parsed = _unwrap_structured_value(value)
    raw_results: list[Any] = []

    if isinstance(parsed, list):
        raw_results = parsed
    elif isinstance(parsed, dict):
        for key in ("results", "items", "entries", "documents", "hits", "sources"):
            nested = parsed.get(key)
            if isinstance(nested, list):
                raw_results = nested
                break

    results: list[dict[str, Any]] = []
    for entry in raw_results:
        normalized = _normalize_result_entry(entry)
        if normalized:
            results.append(normalized)
    return results


def extract_web_search_payload(item: dict[str, Any]) -> dict[str, Any]:
    action = item.get("action") if isinstance(item.get("action"), dict) else {}
    candidate_values = [
        item.get("results"),
        item.get("result"),
        item.get("output"),
        item.get("content"),
        item.get("response"),
        action.get("results"),
        action.get("result"),
        action.get("output"),
        action.get("content"),
    ]
    candidate_records = [
        parsed
        for value in candidate_values
        for parsed in [_unwrap_structured_value(value)]
        if isinstance(parsed, dict)
    ]

    queries = _dedupe_strings(
        [
            *(action.get("queries") if isinstance(action.get("queries"), list) else []),
            action.get("query"),
            item.get("query"),
            *[
                query
                for record in candidate_records
                for query in (
                    *(record.get("queries") if isinstance(record.get("queries"), list) else []),
                    record.get("query"),
                    record.get("question"),
                )
            ],
        ]
    )

    query = _pick_string(
        item.get("query"),
        action.get("query"),
        *[record.get("query") for record in candidate_records],
        *[record.get("question") for record in candidate_records],
        *(queries[:1]),
    )

    results: list[dict[str, Any]] = []
    for value in candidate_values:
        results = _extract_results(value)
        if results:
            break

    summary = _pick_string(
        item.get("summary"),
        item.get("text"),
        action.get("summary"),
        *[record.get("summary") for record in candidate_records],
        *[record.get("text") for record in candidate_records],
        *[record.get("message") for record in candidate_records],
        *[
            value
            for value in (item.get("output"), item.get("content"))
            if isinstance(value, str)
        ],
    )
    error = _pick_string(
        item.get("error"),
        action.get("error"),
        *[record.get("error") for record in candidate_records],
    )

    count = next(
        (
            value
            for value in [*[(record.get("count")) for record in candidate_records], len(results)]
            if isinstance(value, int)
        ),
        len(results),
    )

    payload: dict[str, Any] = {
        "query": query,
        "queries": queries,
        "action_type": action.get("type") if isinstance(action, dict) else None,
        "count": count,
    }
    if isinstance(action, dict) and action:
        payload["action"] = action
    if summary:
        payload["summary"] = summary
    if error:
        payload["error"] = error
    if results:
        payload["results"] = results
    return payload
