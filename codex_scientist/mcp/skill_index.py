"""Bounded skill index for CodexScientist MCP lazy loading."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SkillCard:
    skill_id: str
    title: str
    path: Path
    description: str
    category: str


def _canonical_skill_id(path: Path) -> str:
    name = path.parent.name
    if name.startswith("codexscientist-"):
        return "codexscientist-" + name[len("codexscientist-"):]
    return name


def _read_description(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip().strip('"')
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("---") and not line.startswith("name:"):
            return line[:240]
    return "CodexScientist skill"


def iter_skill_cards() -> list[SkillCard]:
    cards: list[SkillCard] = []
    for skill_file in sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md")):
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        skill_id = _canonical_skill_id(skill_file)
        cards.append(
            SkillCard(
                skill_id=skill_id,
                title=skill_id.replace("-", " ").title(),
                path=skill_file,
                description=_read_description(text),
                category=skill_file.parent.parent.name,
            )
        )
    return cards


def _score(card: SkillCard, query: str, must_have: list[str], must_not: list[str]) -> int:
    haystack = f"{card.skill_id} {card.title} {card.description}".lower()
    if any(term.lower() in haystack for term in must_not):
        return -10_000
    if must_have and not all(term.lower() in haystack for term in must_have):
        return -10_000
    tokens = re.findall(r"[a-zA-Z0-9_\-]+", query.lower())
    score = 0
    for token in tokens:
        if token in haystack:
            score += 3 if token in card.skill_id.lower() else 1
    if "codexscientist" in card.skill_id:
        score += 2
    return score


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


def search_skills(payload: dict[str, Any]) -> dict[str, Any]:
    query = " ".join(
        str(payload.get(key) or "")
        for key in ("raw_user_request", "description_query", "workflow_query")
    )
    limit = max(1, min(int(payload.get("limit") or 5), 10))
    max_chars = max(500, min(int(payload.get("max_chars") or 4000), 8000))
    must_have = [str(item) for item in payload.get("must_have") or []]
    must_not = [str(item) for item in payload.get("must_not") or []]
    ranked = [(_score(card, query, must_have, must_not), card) for card in iter_skill_cards()]
    ranked = [(score, card) for score, card in ranked if score > -10_000]
    ranked.sort(key=lambda item: (-item[0], item[1].skill_id))
    candidates = []
    used = 0
    for score, card in ranked[:limit]:
        candidate = {
            "skill_id": card.skill_id,
            "title": card.title,
            "description": card.description[:280],
            "score": score,
            "handle": _handle_for(card.skill_id),
        }
        estimated = len(str(candidate))
        if used + estimated > max_chars and candidates:
            break
        used += estimated
        candidates.append(candidate)
    return {"ok": True, "candidates": candidates, "tokens_estimate": used}


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
    full = card.path.read_text(encoding="utf-8", errors="replace")
    if view == "preview":
        content = f"# {card.title}\n\n{card.description}\n"
    elif view == "risk":
        lines = [line for line in full.splitlines() if any(key in line.lower() for key in ("risk", "pitfall", "warning", "forbid", "must"))]
        content = "\n".join(lines) or card.description
    elif view == "runtime":
        content = full
    elif view == "sections":
        wanted = {str(item).lower() for item in payload.get("sections") or []}
        lines = []
        keep = not wanted
        for line in full.splitlines():
            if line.startswith("#"):
                keep = not wanted or any(want in line.lower() for want in wanted)
            if keep:
                lines.append(line)
        content = "\n".join(lines)
    elif view == "full":
        if payload.get("allow_full") is not True:
            return {
                "ok": False,
                "error": "full skill view requires allow_full=true",
                "error_type": "full_view_requires_explicit_allow",
                "recoverable": True,
                "suggested_next_action": "Use preview/runtime/risk first, or pass allow_full=true with a max_chars budget.",
            }
        content = full
    else:
        return {"ok": False, "error": f"Unknown view: {view}", "error_type": "invalid_view"}
    source_sha256 = hashlib.sha256(full.encode("utf-8")).hexdigest()
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
        "source_sha256": source_sha256,
    }
