"""Bounded skill index for CodexScientist MCP lazy loading."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_CACHE_VERSION = 1
_SKILL_CACHE: dict[str, tuple[tuple[tuple[str, int, int], ...], list["SkillCard"]]] = {}
_CACHE_HITS = 0
_CACHE_INVALIDATIONS = 0


@dataclass(frozen=True)
class SkillCard:
    skill_id: str
    title: str
    path: Path
    description: str
    category: str
    content: str
    sections: dict[str, str]
    source_sha256: str
    updated_at: str
    trust_level: str
    risk_flags: list[str]
    use_when: str
    do_not_use_when: str
    required_context: str


def _canonical_skill_id(path: Path) -> str:
    name = path.parent.name
    if name.startswith("codexscientist-"):
        return "codexscientist-" + name[len("codexscientist-"):]
    return name


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip().strip('"')
    return meta, text[end + 4:].lstrip("\n")


def _read_description(text: str, meta: dict[str, str]) -> str:
    if meta.get("description"):
        return meta["description"]
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("---") and not line.startswith("name:"):
            return line[:240]
    return "CodexScientist skill"


def _sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "overview"
    sections[current] = []
    for line in body.splitlines():
        if line.startswith("#"):
            current = line.lstrip("#").strip().lower() or "section"
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items() if "\n".join(value).strip()}


def _line_after(body: str, prefix: str) -> str:
    lower_prefix = prefix.lower()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(lower_prefix):
            return stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
    return ""


def _risk_flags(body: str) -> list[str]:
    lower = body.lower()
    flags: list[str] = []
    if any(term in lower for term in ("delete", "destructive", "force push", "remove file")):
        flags.append("destructive_action")
    if any(term in lower for term in ("network", "download", "api", "external")):
        flags.append("network_or_external_io")
    if any(term in lower for term in ("full log", "raw log", "full skill", "long context")):
        flags.append("long_context_risk")
    if any(term in lower for term in ("must", "forbid", "warning", "pitfall", "risk")):
        flags.append("procedural_constraints")
    return flags


def _trust_level(path: Path) -> str:
    try:
        path.resolve().relative_to((PLUGIN_ROOT / "skills").resolve())
        return "repo"
    except ValueError:
        return "user"


def _updated_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).replace(microsecond=0).isoformat()


def _skill_files(root: Path) -> list[Path]:
    return sorted(root.glob("*/SKILL.md"))


def _cache_key(root: Path) -> str:
    return f"v{_CACHE_VERSION}:{root.resolve()}"


def _cache_signature(root: Path) -> tuple[tuple[str, int, int], ...]:
    signature: list[tuple[str, int, int]] = []
    for path in _skill_files(root):
        stat = path.stat()
        signature.append((str(path.resolve()), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


def clear_skill_cache() -> None:
    global _CACHE_HITS, _CACHE_INVALIDATIONS
    _SKILL_CACHE.clear()
    _CACHE_HITS = 0
    _CACHE_INVALIDATIONS = 0


def skill_cache_info() -> dict[str, int]:
    return {"entries": len(_SKILL_CACHE), "hits": _CACHE_HITS, "invalidations": _CACHE_INVALIDATIONS}


def _parse_skill_cards(root: Path) -> list[SkillCard]:
    cards: list[SkillCard] = []
    for skill_file in _skill_files(root):
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        meta, body = _frontmatter(text)
        skill_id = _canonical_skill_id(skill_file)
        source_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cards.append(
            SkillCard(
                skill_id=skill_id,
                title=skill_id.replace("-", " ").title(),
                path=skill_file,
                description=_read_description(body or text, meta),
                category=skill_file.parent.parent.name,
                content=text,
                sections=_sections(body),
                source_sha256=source_sha256,
                updated_at=_updated_at(skill_file),
                trust_level=_trust_level(skill_file),
                risk_flags=_risk_flags(body),
                use_when=_line_after(body, "Use when") or _read_description(body or text, meta),
                do_not_use_when=_line_after(body, "Do not use when") or "the request is unrelated to this procedure",
                required_context=_line_after(body, "Required context") or "project root and current task objective",
            )
        )
    return cards


def iter_skill_cards(skills_root: Path | None = None) -> list[SkillCard]:
    global _CACHE_HITS, _CACHE_INVALIDATIONS
    root = skills_root or (PLUGIN_ROOT / "skills")
    key = _cache_key(root)
    signature = _cache_signature(root)
    cached = _SKILL_CACHE.get(key)
    if cached and cached[0] == signature:
        _CACHE_HITS += 1
        return list(cached[1])
    if cached:
        _CACHE_INVALIDATIONS += 1
    cards = _parse_skill_cards(root)
    _SKILL_CACHE[key] = (signature, cards)
    return list(cards)


def _tokens(query: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_\-]+", query.lower())


def _expand_query(query: str) -> str:
    additions: list[str] = []
    if any(term in query for term in ("恢复", "继续", "上下文", "压缩", "断点", "续跑")):
        additions.append("codexscientist-codex mcp status context pack recovery state resume checkpoint delta")
    if any(term in query for term in ("审查", "评审", "证据", "claim", "review")):
        additions.append("review claim evidence verdict")
    if any(term in query for term in ("基线", "baseline", "metric", "指标")):
        additions.append("baseline metric manifest gate")
    return " ".join([query, *additions]).strip()


def _score(card: SkillCard, query: str, must_not: list[str]) -> tuple[int, list[str], list[str]]:
    fields = {
        "skill_id": card.skill_id.lower(),
        "title": card.title.lower(),
        "description": card.description.lower(),
        "workflow": " ".join(card.sections.values()).lower(),
    }
    lowered_query = query.lower()
    if card.skill_id.lower() in lowered_query:
        exact_bonus = 80
    else:
        exact_bonus = 0
    for term in must_not:
        term_lower = term.lower()
        if term_lower and any(term_lower in value for value in fields.values()):
            return -10_000, [], [f"must_not:{term}"]
    score = exact_bonus
    matched_fields: list[str] = []
    why_match: list[str] = []
    for token in _tokens(query):
        for field, value in fields.items():
            if token in value:
                score += 5 if field == "skill_id" else 2 if field == "title" else 1
                if field not in matched_fields:
                    matched_fields.append(field)
                if len(why_match) < 4:
                    why_match.append(f"{token} matched {field}")
                break
    return score, why_match, matched_fields


def _confidence(score: int) -> str:
    if score >= 12:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


def _candidate(card: SkillCard, score: int, why_match: list[str], matched_fields: list[str], missing: list[str], why_maybe_not: list[str]) -> dict[str, Any]:
    confidence = _confidence(score)
    if why_maybe_not:
        load_decision = "do_not_auto_load"
    elif missing or confidence != "high":
        load_decision = "preview_first"
    else:
        load_decision = "safe_to_load"
    recommended_view = "runtime" if load_decision == "safe_to_load" else "preview"
    data = {
        "skill_id": card.skill_id,
        "title": card.title,
        "description": card.description[:280],
        "score": score,
        "handle": _handle_for(card.skill_id),
        "confidence": confidence,
        "load_decision": load_decision,
        "recommended_view": recommended_view,
        "why_match": why_match,
        "why_maybe_not": why_maybe_not,
        "missing_requirements": missing,
        "matched_fields": matched_fields,
        "risk_flags": card.risk_flags,
        "trust_level": card.trust_level,
        "source_hash": card.source_sha256,
        "source_sha256": card.source_sha256,
        "updated_at": card.updated_at,
        "tokens_estimate": 0,
        "truncated": False,
    }
    data["tokens_estimate"] = len(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return data


def _handle_for(skill_id: str) -> str:
    digest = hashlib.sha256(f"codexscientist-skill:{skill_id}".encode()).hexdigest()[:12]
    return f"skill:{digest}:{skill_id}"


def _skill_id_from_handle(handle: str) -> str | None:
    parts = handle.split(":", 2)
    if len(parts) != 3 or parts[0] != "skill":
        return None
    expected = _handle_for(parts[2])
    return parts[2] if expected == handle else None


def _valid_skill_id(skill_id: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9\-]{0,96}", skill_id)) and ".." not in skill_id


def search_skill_cards(payload: dict[str, Any], *, skills_root: Path | None = None) -> dict[str, Any]:
    query = _expand_query(" ".join(
        str(payload.get(key) or "")
        for key in ("raw_user_request", "description_query", "workflow_query")
    ))
    limit = max(1, min(int(payload.get("limit") or 5), 10))
    max_chars = max(500, min(int(payload.get("max_chars") or 4000), 8000))
    must_have = [str(item) for item in payload.get("must_have") or []]
    must_not = [str(item) for item in payload.get("must_not") or []]
    ranked = []
    for card in iter_skill_cards(skills_root):
        score, why_match, matched_fields = _score(card, query, must_not)
        if score <= -10_000:
            continue
        haystack = f"{card.skill_id} {card.title} {card.description} {' '.join(card.sections.values())}".lower()
        missing = [term for term in must_have if term.lower() not in haystack]
        why_maybe_not: list[str] = []
        if any(term in query.lower() for term in ("不要", "not ", "do not")):
            for term in ("resume", "checkpoint", "review", "baseline"):
                if term in card.skill_id and term in query.lower() and f"not {term}" in query.lower():
                    why_maybe_not.append(f"negative cue for {term}")
        ranked.append((score, card, why_match, matched_fields, missing, why_maybe_not))
    ranked.sort(key=lambda item: (-item[0], item[1].skill_id))
    candidates: list[dict[str, Any]] = []
    used = 0
    response_truncated = False
    for score, card, why_match, matched_fields, missing, why_maybe_not in ranked[:limit]:
        candidate = _candidate(card, score, why_match, matched_fields, missing, why_maybe_not)
        estimated = int(candidate["tokens_estimate"])
        if used + estimated > max_chars and candidates:
            response_truncated = True
            break
        if used + estimated > max_chars:
            candidate["truncated"] = True
            response_truncated = True
        used += estimated
        candidates.append(candidate)
    return {"ok": True, "candidates": candidates, "tokens_estimate": min(used, max_chars), "truncated": response_truncated}


def search_skills(payload: dict[str, Any]) -> dict[str, Any]:
    return search_skill_cards(payload)


def _applicability(card: SkillCard) -> str:
    return "\n".join(
        [
            f"Use when: {card.use_when}",
            f"Do not use when: {card.do_not_use_when}",
            f"Required context: {card.required_context}",
            "",
        ]
    )


def _runtime_content(card: SkillCard) -> str:
    wanted = ("runtime", "step", "workflow", "process", "verification", "pitfall", "risk", "checklist")
    blocks: list[str] = []
    for heading, body in card.sections.items():
        if any(term in heading for term in wanted):
            blocks.append(f"## {heading.title()}\n{body}")
    if not blocks:
        overview = card.sections.get("overview") or card.description
        blocks.append(f"## Runtime Summary\n{overview}")
    return _applicability(card) + "\n\n".join(blocks)


def _preview_content(card: SkillCard) -> str:
    return _applicability(card) + f"Summary: {card.description}\nRisk flags: {', '.join(card.risk_flags) or 'none'}\n"


def _risk_content(card: SkillCard) -> str:
    return _applicability(card) + "\n".join(
        [
            f"Trust level: {card.trust_level}",
            f"Risk flags: {', '.join(card.risk_flags) or 'none'}",
            f"Source sha256: {card.source_sha256}",
        ]
    )


def load_skill(payload: dict[str, Any]) -> dict[str, Any]:
    handle = str(payload.get("handle") or payload.get("skill_id") or "")
    if handle.startswith("skill:"):
        skill_id = _skill_id_from_handle(handle)
        if not skill_id:
            return {"ok": False, "error": "Invalid or forged skill handle", "error_type": "invalid_handle"}
    elif ":" in handle:
        return {"ok": False, "error": "Invalid or forged skill handle", "error_type": "invalid_handle"}
    elif handle:
        skill_id = handle
    else:
        return {"ok": False, "error": "Missing skill handle or skill_id", "error_type": "missing_argument"}
    cards = {card.skill_id: card for card in iter_skill_cards()}
    if not _valid_skill_id(skill_id):
        return {"ok": False, "error": "Invalid skill id", "error_type": "invalid_handle"}
    card = cards.get(skill_id)
    if not card:
        return {"ok": False, "error": f"Unknown skill: {skill_id}", "error_type": "unknown_skill"}
    view = str(payload.get("view") or "preview")
    max_chars = max(80, min(int(payload.get("max_chars") or 4000), 16000))
    if view == "card":
        content = f"{card.title}: {card.description}\n"
    elif view == "preview":
        content = _preview_content(card)
    elif view == "risk":
        content = _risk_content(card)
    elif view == "runtime":
        content = _runtime_content(card)
    elif view == "sections":
        wanted = {str(item).lower() for item in payload.get("sections") or []}
        blocks = []
        for heading, body in card.sections.items():
            if not wanted or any(want in heading for want in wanted):
                blocks.append(f"## {heading.title()}\n{body}")
        content = _applicability(card) + "\n\n".join(blocks)
    elif view == "full":
        if payload.get("allow_full") is not True:
            return {
                "ok": False,
                "error": "full skill view requires allow_full=true",
                "error_type": "full_view_requires_explicit_allow",
                "recoverable": True,
                "suggested_next_action": "Use preview/runtime/risk first, or pass allow_full=true with a max_chars budget.",
            }
        content = _applicability(card) + card.content
    else:
        return {"ok": False, "error": f"Unknown view: {view}", "error_type": "invalid_view"}
    truncated = len(content) > max_chars
    content = content[:max_chars]
    return {
        "ok": True,
        "skill_id": skill_id,
        "view": view,
        "content": content,
        "tokens_estimate": len(content),
        "truncated": truncated,
        "source_path": str(card.path),
        "source_sha256": card.source_sha256,
        "updated_at": card.updated_at,
        "trust_level": card.trust_level,
        "risk_flags": card.risk_flags,
    }
