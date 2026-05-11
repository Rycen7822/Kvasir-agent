#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, datetime as dt, difflib, json, os, re, sys, time
from html import unescape
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote
import xml.etree.ElementTree as ET
import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_RANKING_DIR = Path("/home/xu/project/ds_dev/paper_reliability_verifier_skill/paper_ranking")
FALLBACK_RANKING_DIR = ROOT / "paper_ranking"
LEGACY_VENUE_CSV = ROOT / "data" / "curated_venue_ranks.sample.csv"
LEGACY_JOURNAL_CSV = ROOT / "data" / "journal_rank_overrides.sample.csv"


def ranking_dir() -> Path:
    """Return the canonical local ranking snapshot directory.

    Primary production location is intentionally outside this draft skill so the
    ranking CSVs can be updated without editing verifier code. The skill-local
    paper_ranking directory is kept as a fallback for portability/tests.
    """
    env = os.getenv("PAPER_RANKING_DIR")
    if env:
        return Path(env).expanduser()
    if DEFAULT_PROJECT_RANKING_DIR.exists():
        return DEFAULT_PROJECT_RANKING_DIR
    return FALLBACK_RANKING_DIR


def conference_ranking_csv() -> Path:
    return ranking_dir() / "conference_ranking.csv"


def journal_ranking_csv() -> Path:
    return ranking_dir() / "journal_ranking.csv"

def today(): return dt.date.today().isoformat()

def norm(s: Optional[str]) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_similarity(a: Optional[str], b: Optional[str]) -> float:
    na, nb = norm(unescape(a or "")), norm(unescape(b or ""))
    if not na or not nb: return 0.0
    if na == nb: return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()

def get_json(url, params=None, headers=None, retries=2):
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=20)
            if r.status_code == 404: return None
            if r.status_code in (429, 500, 502, 503, 504) and i < retries:
                time.sleep(i + 1); continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if i == retries: return {"_error": f"{type(e).__name__}: {e}"}
            time.sleep(i + 1)

def load_csv(path: Path):
    if not path.exists(): return []
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))


def load_ranking_csv(path: Path):
    rows = load_csv(path)
    if rows:
        return rows
    # Legacy sample files are plain UTF-8 and keep the old draft usable.
    if path == conference_ranking_csv():
        return load_csv(LEGACY_VENUE_CSV)
    if path == journal_ranking_csv():
        return load_csv(LEGACY_JOURNAL_CSV)
    return []

def openalex(doi):
    p = {}
    if os.getenv("OPENALEX_MAILTO"): p["mailto"] = os.getenv("OPENALEX_MAILTO")
    return get_json(f"https://api.openalex.org/works/doi:{quote(doi, safe='/:.')}", p)


def openalex_title_search(title=None, year=None, rows=5):
    if not title:
        return []
    p = {"search": title, "per-page": min(max(rows, 1), 20)}
    if year:
        p["filter"] = f"from_publication_date:{year}-01-01,to_publication_date:{year}-12-31"
    if os.getenv("OPENALEX_MAILTO"):
        p["mailto"] = os.getenv("OPENALEX_MAILTO")
    data = get_json("https://api.openalex.org/works", p)
    if not isinstance(data, dict) or data.get("_error"):
        return []
    return data.get("results") or []


def choose_openalex_work(candidates, title=None, year=None, min_title_similarity=0.90):
    hits = [c for c in (candidates or []) if isinstance(c, dict)]
    if not hits:
        return None
    for h in hits:
        sim = title_similarity(title, h.get("display_name") or h.get("title")) if title else 0.0
        pub_year = h.get("publication_year")
        if title and sim >= min_title_similarity and (not year or pub_year == year):
            return h
    best = hits[0]
    if title and title_similarity(title, best.get("display_name") or best.get("title")) >= min_title_similarity:
        return best
    return None


def semantic_scholar(doi):
    fields = "title,year,citationCount,influentialCitationCount,referenceCount,venue,publicationVenue,externalIds,fieldsOfStudy,authors,publicationTypes"
    h = {}
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"): h["x-api-key"] = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    return get_json(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='/')}", {"fields": fields}, h)


def semantic_scholar_arxiv(arxiv_id):
    fields = "title,year,citationCount,influentialCitationCount,referenceCount,venue,publicationVenue,externalIds,fieldsOfStudy,authors,publicationTypes"
    h = {}
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"): h["x-api-key"] = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    return get_json(f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{quote(arxiv_id, safe='/')}", {"fields": fields}, h)


def arxiv_id_from_url(raw):
    text = clean_cell(raw)
    if not text:
        return ""
    m = re.search(r"(?:arxiv\.org/(?:abs|pdf)/|arXiv:)([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/[0-9]{7}(?:v\d+)?)", text, re.I)
    if m:
        return m.group(1).removesuffix(".pdf")
    if re.fullmatch(r"[0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/[0-9]{7}(?:v\d+)?", text, re.I):
        return text.removesuffix(".pdf")
    return ""


def arxiv_doi_from_id(arxiv_id):
    clean = re.sub(r"v\d+$", "", clean_cell(arxiv_id))
    return f"10.48550/arXiv.{clean}" if clean else None

def crossref_headers():
    h = {}
    mailto = os.getenv("CROSSREF_MAILTO")
    if mailto:
        # Crossref REST API recommends identifying clients with mailto for the polite pool.
        h["User-Agent"] = f"paper-reliability-verifier/0.1 (mailto:{mailto})"
    return h


def crossref_params(extra=None):
    p = dict(extra or {})
    if os.getenv("CROSSREF_MAILTO"):
        p["mailto"] = os.getenv("CROSSREF_MAILTO")
    return p


def crossref(doi):
    d = get_json(f"https://api.crossref.org/v1/works/{quote(doi, safe='')}", crossref_params(), crossref_headers())
    if d is None:
        return {"_error": "crossref_not_found"}
    return d.get("message") if isinstance(d, dict) and "message" in d else d


def crossref_work_search(title=None, year=None, rows=5):
    """Search Crossref /works for title-based fallback metadata.

    Swagger endpoint: GET https://api.crossref.org/works with query, filter,
    select, rows, sort, and mailto parameters. We use query.title when accepted
    by the API and keep result selection small to avoid broad, noisy matches.
    """
    if not title:
        return []
    params = {
        "query.title": title,
        "rows": min(max(rows, 1), 20),
        "sort": "score",
        "order": "desc",
        "select": "DOI,title,type,container-title,short-container-title,event,published,published-print,published-online,issued,is-referenced-by-count,update-to,relation,ISSN,ISBN,publisher,URL",
    }
    if year:
        params["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
    data = get_json("https://api.crossref.org/v1/works", crossref_params(params), crossref_headers())
    if not isinstance(data, dict) or data.get("_error"):
        return []
    return ((data.get("message") or {}).get("items") or [])


def crossref_date_year(work):
    for k in ["published", "published-print", "published-online", "issued"]:
        parts = (((work or {}).get(k) or {}).get("date-parts") or [[]])[0]
        if parts and isinstance(parts[0], int):
            return parts[0]
    return None


def crossref_title(work):
    titles = (work or {}).get("title") or []
    return clean_cell(titles[0]) if titles else ""


def crossref_venue_name(work, venue_type=None):
    event_name = ((work or {}).get("event") or {}).get("name")
    container = ((work or {}).get("container-title") or [])
    if venue_type == "conference" and event_name:
        return clean_cell(event_name)
    if container:
        return clean_cell(container[0])
    return clean_cell(event_name)


def crossref_venue_type(work):
    typ = norm((work or {}).get("type"))
    container = norm(" ".join((work or {}).get("container-title") or []))
    event_name = norm(((work or {}).get("event") or {}).get("name"))
    if typ in {"posted content", "posted-content"} or any(k in container for k in ["arxiv", "biorxiv", "medrxiv", "preprint"]):
        return "preprint"
    if typ in {"journal article", "journal-article"}:
        return "journal"
    if typ in {"proceedings article", "proceedings-article"} or event_name or any(k in container for k in ["proceedings", "conference", "symposium", "workshop"]):
        return "conference"
    return "auto"


def crossref_hit_summary(work, reason=None, title=None, year=None):
    vtype = crossref_venue_type(work)
    short = ((work or {}).get("short-container-title") or [])
    venue = crossref_venue_name(work, vtype)
    acronym = clean_cell(short[0]) if short else ""
    if not acronym and venue:
        m = re.search(r"\(([A-Z][A-Z0-9&+.-]{1,15})\)\s*$", venue)
        if m:
            acronym = m.group(1)
    return {
        "doi": clean_cell((work or {}).get("DOI")),
        "title": crossref_title(work),
        "title_similarity": round(title_similarity(title, crossref_title(work)), 4) if title else 0.0,
        "year": crossref_date_year(work),
        "year_match": bool(year and crossref_date_year(work) == year),
        "type": clean_cell((work or {}).get("type")),
        "subtype": clean_cell((work or {}).get("subtype")),
        "venue_name": venue,
        "short_container_title": acronym,
        "event": (work or {}).get("event") or {},
        "publisher": clean_cell((work or {}).get("publisher")),
        "issn": (work or {}).get("ISSN") or [],
        "isbn": (work or {}).get("ISBN") or [],
        "is_referenced_by_count": (work or {}).get("is-referenced-by-count"),
        "updates": (work or {}).get("update-to") or [],
        "relation": (work or {}).get("relation") or {},
        "url": clean_cell((work or {}).get("URL")),
        "match_reason": reason,
    }


def choose_crossref_work(candidates, title=None, doi=None, year=None, min_title_similarity=0.92):
    hits = [c for c in (candidates or []) if isinstance(c, dict)]
    if not hits:
        return None, "no_crossref_hit"
    for h in hits:
        if doi and norm(h.get("DOI")) == norm(doi):
            return h, "doi_match"
    for h in hits:
        sim = title_similarity(title, crossref_title(h)) if title else 0.0
        y = crossref_date_year(h)
        if title and sim >= min_title_similarity and (not year or y == year):
            return h, "title_year_match" if year else "title_match"
    best = hits[0]
    if title and title_similarity(title, crossref_title(best)) >= min_title_similarity:
        return best, "title_match_best"
    return None, "ambiguous_or_low_similarity"


def crossref_detect_accepted_publication(doi=None, title=None, year=None, cr=None):
    candidates = []
    if cr and not cr.get("_error"):
        candidates.append(cr)
    elif doi:
        work = crossref(doi)
        if work and not work.get("_error"):
            candidates.append(work)
    elif title:
        candidates.extend(crossref_work_search(title=title, year=year))
    hit, reason = choose_crossref_work(candidates, title=title, doi=doi, year=year)
    if not hit:
        return {
            "status": "crossref_not_found_or_ambiguous",
            "venue_name": None,
            "venue_type": "auto",
            "acronym": "",
            "evidence_source": f"crossref works API: {reason}",
            "interface_version": "accepted-publication-v1",
            "crossref": {"reason": reason, "top_hits": [crossref_hit_summary(h, title=title, year=year) for h in candidates[:3]]},
        }
    vtype = crossref_venue_type(hit)
    summary = crossref_hit_summary(hit, reason=reason, title=title, year=year)
    if vtype == "auto":
        return {
            "status": "crossref_not_found_or_ambiguous",
            "venue_name": None,
            "venue_type": "auto",
            "acronym": "",
            "evidence_source": f"crossref works API: unsupported_type:{summary.get('type') or 'unknown'}",
            "interface_version": "accepted-publication-v1",
            "crossref": {"reason": "unsupported_type", "top_hits": [summary]},
        }
    status = "crossref_confirmed" if vtype in {"conference", "journal"} else "crossref_preprint_or_unclassified"
    return {
        "status": status,
        "venue_name": summary.get("venue_name") or None,
        "venue_type": vtype,
        "acronym": summary.get("short_container_title") or "",
        "evidence_source": f"crossref works API: {reason}",
        "interface_version": "accepted-publication-v1",
        "crossref": summary,
    }


def title_from(oa, ss, cr, fallback=None):
    for s in [oa, ss, cr]:
        if not s or s.get("_error"): continue
        if isinstance(s.get("display_name"), str): return s["display_name"]
        if isinstance(s.get("title"), str): return s["title"]
        if isinstance(s.get("title"), list) and s["title"]: return s["title"][0]
    return fallback

def year_from(oa, ss, cr, fallback=None):
    for s in [oa, ss, cr]:
        if not s or s.get("_error"): continue
        for k in ["publication_year", "year"]:
            if isinstance(s.get(k), int): return s[k]
        for k in ["published-print","published-online","published","issued"]:
            parts = (((s.get(k) or {}).get("date-parts") or [[]])[0])
            if parts and isinstance(parts[0], int): return parts[0]
    return fallback

def source_name(oa, ss, cr):
    if oa and not oa.get("_error"):
        src = ((oa.get("primary_location") or {}).get("source") or {})
        if src.get("display_name"): return src["display_name"]
    if ss and not ss.get("_error"):
        if (ss.get("publicationVenue") or {}).get("name"): return ss["publicationVenue"]["name"]
        if ss.get("venue"): return ss["venue"]
    if cr and not cr.get("_error"):
        if cr.get("container-title"): return cr["container-title"][0]
        if (cr.get("event") or {}).get("name"): return cr["event"]["name"]
    return None


def as_list(x):
    if x is None: return []
    return x if isinstance(x, list) else [x]


ACL_VENUE_IDS = {"acl", "emnlp", "naacl", "eacl", "aacl", "coling", "conll", "tacl", "cl"}

OPENREVIEW_VENUE_NAMES = {
    "ICLR": "International Conference on Learning Representations",
    "TMLR": "Transactions on Machine Learning Research",
    "COLM": "Conference on Language Modeling",
    "UAI": "Conference on Uncertainty in Artificial Intelligence",
}


def content_value(content: dict, key: str, default=None):
    v = (content or {}).get(key, default)
    if isinstance(v, dict) and "value" in v:
        return v.get("value", default)
    return v


def load_env_file(path: Path):
    """Load simple KEY=VALUE env files without printing secrets."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def openreview_client(api_version="v2"):
    try:
        load_env_file(Path("/home/xu/.hermes/secrets/openreview.env"))
        import openreview  # type: ignore
        cls = openreview.api.OpenReviewClient if api_version == "v2" else openreview.Client
        baseurl = "https://api2.openreview.net" if api_version == "v2" else "https://api.openreview.net"
        username = os.getenv("OPENREVIEW_USERNAME") or None
        password = os.getenv("OPENREVIEW_PASSWORD") or None
        return cls(baseurl=baseurl, username=username, password=password)
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


def openreview_acronym_from_venue_id(venue_id: Optional[str]) -> str:
    if not venue_id: return ""
    first = venue_id.split(".", 1)[0]
    return norm_acronym(first)


def openreview_venue_name(venue_id: Optional[str], venue_label: Optional[str] = None) -> str:
    acronym = openreview_acronym_from_venue_id(venue_id)
    return OPENREVIEW_VENUE_NAMES.get(acronym) or clean_cell(venue_label) or clean_cell(venue_id)


def classify_openreview_presentation_type(text: Optional[str]):
    t = norm(text)
    if not t: return None
    if "reject" in t: return "rejected"
    if "oral" in t: return "oral"
    if "spotlight" in t: return "spotlight"
    if "poster" in t: return "poster"
    if "accept" in t: return "accepted_unknown_presentation_type"
    return None


def openreview_note_to_hit(note, title=None, year=None):
    content = getattr(note, "content", {}) or {}
    note_title = clean_cell(content_value(content, "title"))
    venue_id = clean_cell(content_value(content, "venueid"))
    venue_label = clean_cell(content_value(content, "venue"))
    decision_values = []
    for reply in ((getattr(note, "details", {}) or {}).get("replies") or (getattr(note, "details", {}) or {}).get("directReplies") or []):
        invitations = reply.get("invitations") or [reply.get("invitation", "")]
        if any(str(inv).endswith("Decision") for inv in invitations):
            decision_values.append(clean_cell(content_value(reply.get("content") or {}, "decision")))
    evidence_text = " ".join([venue_label, venue_id] + decision_values)
    presentation = classify_openreview_presentation_type(evidence_text)
    accepted = bool((presentation in {"oral", "spotlight", "poster", "accepted_unknown_presentation_type"}) or (venue_id and "/Rejected" not in venue_id and "/Withdrawn" not in venue_id and "/Desk_Rejected" not in venue_id and norm(openreview_acronym_from_venue_id(venue_id)) in norm(venue_id)))
    if presentation == "rejected":
        accepted = False
    return {
        "openreview_id": clean_cell(getattr(note, "id", "")),
        "forum": clean_cell(getattr(note, "forum", "")),
        "number": getattr(note, "number", None),
        "title": note_title,
        "title_similarity": round(title_similarity(title, note_title), 4) if title else 0.0,
        "year_match": bool(year and str(year) in " ".join([venue_id, venue_label])),
        "venueid": venue_id,
        "venue_label": venue_label,
        "decision_notes": decision_values,
        "accepted": accepted,
        "presentation_type": presentation,
        "url": f"https://openreview.net/forum?id={clean_cell(getattr(note, 'forum', '') or getattr(note, 'id', ''))}" if clean_cell(getattr(note, "forum", "") or getattr(note, "id", "")) else "",
    }


def openreview_candidate_venue_ids(year=None, explicit_venue_id=None):
    if explicit_venue_id:
        return [explicit_venue_id]
    env = os.getenv("OPENREVIEW_VENUE_IDS")
    if env:
        return [x.strip() for x in re.split(r"[,;\s]+", env) if x.strip()]
    return []


def openreview_publication_search(title=None, year=None, venue_id=None, client=None, limit=10):
    venue_ids = openreview_candidate_venue_ids(year=year, explicit_venue_id=venue_id)
    if not venue_ids:
        return {"status": "missing_venue_id", "hits": []}
    client = client or openreview_client("v2")
    if isinstance(client, dict) and client.get("_error"):
        return {"status": "client_error", "error": client["_error"], "hits": []}
    hits = []
    errors = []
    for vid in venue_ids:
        try:
            notes = client.get_all_notes(content={"venueid": vid}, details="replies")
            for note in notes:
                hit = openreview_note_to_hit(note, title=title, year=year)
                hit["query_venue_id"] = vid
                hits.append(hit)
        except Exception as e:
            errors.append({"venue_id": vid, "error": f"{type(e).__name__}: {e}"})
    hits.sort(key=lambda x: (x.get("accepted") is True, x.get("title_similarity", 0), x.get("year_match") is True), reverse=True)
    return {"status": "ok" if hits else "no_hits", "query": {"title": title, "year": year, "venue_ids": venue_ids}, "hits": hits[:max(1, limit)], "errors": errors}


def openreview_v1_publication_search(title=None, year=None, venue_id=None, client=None, limit=10):
    venue_ids = openreview_candidate_venue_ids(year=year, explicit_venue_id=venue_id)
    if not venue_ids:
        return {"status": "missing_venue_id", "hits": []}
    client = client or openreview_client("v1")
    if isinstance(client, dict) and client.get("_error"):
        return {"status": "client_error", "error": client["_error"], "hits": []}
    hits = []
    errors = []
    for vid in venue_ids:
        try:
            notes = client.get_all_notes(invitation=f"{vid}/-/Blind_Submission", details="directReplies,original")
            for blind in notes:
                details = getattr(blind, "details", {}) or {}
                original = details.get("original") or blind
                if getattr(original, "details", None) is None:
                    try:
                        original.details = {}
                    except Exception:
                        pass
                if getattr(original, "details", None) is not None:
                    original.details["directReplies"] = details.get("directReplies") or []
                hit = openreview_note_to_hit(original, title=title, year=year)
                hit["query_venue_id"] = vid
                if not hit.get("venueid"):
                    hit["venueid"] = vid
                hits.append(hit)
        except Exception as e:
            errors.append({"venue_id": vid, "error": f"{type(e).__name__}: {e}"})
    hits.sort(key=lambda x: (x.get("accepted") is True, x.get("title_similarity", 0), x.get("year_match") is True), reverse=True)
    return {"status": "ok" if hits else "no_hits", "query": {"title": title, "year": year, "venue_ids": venue_ids, "api": "v1"}, "hits": hits[:max(1, limit)], "errors": errors}


def choose_openreview_hit(search_result, title=None, year=None, min_title_similarity=0.92):
    hits = (search_result or {}).get("hits") or []
    if not hits: return None, "no_openreview_hit"
    for h in hits:
        if title and h.get("title_similarity", 0) >= min_title_similarity and h.get("accepted") is True:
            return h, "accepted_title_match"
    for h in hits:
        if title and h.get("title_similarity", 0) >= min_title_similarity:
            return h, "title_match_not_accepted"
    return None, "ambiguous_or_low_similarity"


def openreview_detect_accepted_publication(title=None, year=None, venue_id=None, client=None):
    result = openreview_publication_search(title=title, year=year, venue_id=venue_id, client=client)
    hit, reason = choose_openreview_hit(result, title=title, year=year)
    if not hit and client is None and venue_id:
        v1_result = openreview_v1_publication_search(title=title, year=year, venue_id=venue_id)
        v1_hit, v1_reason = choose_openreview_hit(v1_result, title=title, year=year)
        if v1_hit:
            result, hit, reason = v1_result, v1_hit, "api1_" + v1_reason
    if not hit:
        return {
            "status": "openreview_not_found_or_ambiguous",
            "venue_name": None,
            "venue_type": "auto",
            "acronym": "",
            "evidence_source": f"OpenReview accepted submissions: {reason}",
            "interface_version": "accepted-publication-v1",
            "openreview": {"query": result.get("query"), "status": result.get("status"), "reason": reason, "top_hits": (result.get("hits") or [])[:3], "errors": result.get("errors") or []},
        }
    if not hit.get("accepted"):
        return {
            "status": "openreview_not_accepted",
            "venue_name": None,
            "venue_type": "conference",
            "acronym": openreview_acronym_from_venue_id(hit.get("query_venue_id") or hit.get("venueid")),
            "evidence_source": f"OpenReview accepted submissions: {reason}",
            "interface_version": "accepted-publication-v1",
            "openreview": hit,
        }
    vid = hit.get("query_venue_id") or hit.get("venueid")
    acronym = openreview_acronym_from_venue_id(vid)
    return {
        "status": "openreview_confirmed",
        "venue_name": openreview_venue_name(vid, hit.get("venue_label")),
        "venue_type": "journal" if acronym == "TMLR" else "conference",
        "acronym": acronym,
        "evidence_source": f"OpenReview accepted submissions: {reason}",
        "interface_version": "accepted-publication-v1",
        "openreview": hit,
    }


def acl_anthology_data_dir() -> Optional[Path]:
    """Locate the ACL Anthology metadata data directory.

    The documented Python API entrypoint is `Anthology.from_repo()`, which
    clones/updates the official metadata repo and exposes `.datadir`. The local
    XML scan below intentionally uses the same data directory but avoids building
    the package's global venue/event indices, which can be slow and can fail when
    the installed package schema lags behind the latest data repository.
    """
    env = os.getenv("ACL_ANTHOLOGY_DATA_DIR")
    if env and Path(env).expanduser().exists():
        return Path(env).expanduser()
    try:
        from acl_anthology import Anthology  # type: ignore
        anthology = Anthology.from_repo(verbose=False)
        datadir = Path(anthology.datadir)
        if datadir.exists():
            return datadir
    except Exception:
        pass
    fallback = Path.home() / ".local/share/acl-anthology/git/acl-org-acl-anthology-git/data"
    return fallback if fallback.exists() else None


def xml_text(elem) -> str:
    return "" if elem is None else re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def load_acl_venue_metadata(datadir: Path) -> dict[str, dict[str, Any]]:
    venues = {}
    venue_dir = datadir / "yaml" / "venues"
    if not venue_dir.exists():
        return venues
    for path in venue_dir.glob("*.yaml"):
        item = {"id": path.stem}
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if ":" not in line or line.startswith(" "):
                    continue
                k, v = line.split(":", 1)
                v = v.strip().strip('"\'')
                if v.lower() in {"true", "false"}:
                    item[k.strip()] = v.lower() == "true"
                elif v:
                    item[k.strip()] = v
        except OSError:
            continue
        venues[path.stem] = item
    return venues


def acl_anthology_publication_search(title=None, doi=None, year=None, limit=10):
    """Search local ACL Anthology metadata by DOI or conservative title match.

    API docs used for semantics: `Anthology.from_repo()`, `Paper.full_id`,
    `Paper.web_url`, `Paper.pdf.url`, `Paper.doi`, and volume venue metadata.
    The actual scan reads the official XML files from the same data dir so it
    stays robust under package/data schema skew.
    """
    datadir = acl_anthology_data_dir()
    if not datadir:
        return {"status": "data_dir_not_found", "hits": []}
    xml_dir = datadir / "xml"
    if not xml_dir.exists():
        return {"status": "xml_dir_not_found", "data_dir": str(datadir), "hits": []}
    venues = load_acl_venue_metadata(datadir)
    hits = []
    files = sorted(xml_dir.glob("*.xml"))
    for path in files:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        collection_id = root.attrib.get("id") or path.stem
        for vol in root.findall("volume"):
            meta = vol.find("meta")
            vol_year = clean_cell(xml_text(meta.find("year") if meta is not None else None))
            if year and vol_year and vol_year != str(year):
                continue
            vol_id = vol.attrib.get("id") or ""
            volume_title = xml_text(meta.find("booktitle") if meta is not None else None)
            volume_url = xml_text(meta.find("url") if meta is not None else None)
            venue_ids = [xml_text(v) for v in (meta.findall("venue") if meta is not None else []) if xml_text(v)]
            venue_meta = [venues.get(v, {"id": v, "acronym": v.upper(), "name": v}) for v in venue_ids]
            for paper in vol.findall("paper"):
                ptitle = xml_text(paper.find("title"))
                pdoi = clean_cell(xml_text(paper.find("doi")))
                pid = paper.attrib.get("id") or ""
                url_id = clean_cell(xml_text(paper.find("url")))
                full_id = url_id or f"{collection_id}-{vol_id}.{pid}"
                doi_match = bool(doi and norm(pdoi) == norm(doi))
                sim = title_similarity(title, ptitle) if title else 0.0
                if not doi_match and (not title or sim < 0.60):
                    continue
                hit_venue = venue_meta[0] if venue_meta else {}
                hit = {
                    "title": ptitle,
                    "title_similarity": round(sim, 4),
                    "year": vol_year or (str(year) if year else ""),
                    "doi": pdoi,
                    "doi_match": doi_match,
                    "year_match": bool(year and (not vol_year or vol_year == str(year))),
                    "anthology_id": full_id,
                    "bibkey": clean_cell(xml_text(paper.find("bibkey"))),
                    "url": f"https://aclanthology.org/{full_id}/" if full_id else "",
                    "pdf_url": f"https://aclanthology.org/{full_id}.pdf" if full_id else "",
                    "venue_ids": venue_ids,
                    "venue_id": hit_venue.get("id") or (venue_ids[0] if venue_ids else ""),
                    "venue_acronym": hit_venue.get("acronym") or ((venue_ids[0].upper()) if venue_ids else ""),
                    "venue_name": hit_venue.get("name") or volume_title,
                    "is_acl_sponsored": bool(hit_venue.get("is_acl")) if hit_venue else None,
                    "is_toplevel_venue": bool(hit_venue.get("is_toplevel")) if hit_venue else None,
                    "volume_id": vol_id,
                    "volume_title": volume_title,
                    "volume_url": f"https://aclanthology.org/{volume_url}/" if volume_url else "",
                    "source_xml": path.name,
                }
                hits.append(hit)
    hits.sort(key=lambda x: (x["doi_match"], x["title_similarity"], x["year_match"], x.get("is_toplevel_venue") is True), reverse=True)
    return {"status": "ok", "data_dir": str(datadir), "query": {"title": title, "doi": doi, "year": year}, "hits": hits[:max(1, limit)], "total_candidates": len(hits)}


def choose_acl_anthology_hit(search_result, title=None, doi=None, year=None, min_title_similarity=0.90):
    hits = (search_result or {}).get("hits") or []
    if not hits: return None, "no_acl_anthology_hit"
    for h in hits:
        if h.get("doi_match"):
            return h, "doi_match"
    for h in hits:
        if title and h.get("title_similarity", 0) >= min_title_similarity and (not year or h.get("year_match")):
            return h, "title_year_match" if year else "title_match"
    best = hits[0]
    if title and best.get("title_similarity", 0) >= min_title_similarity:
        return best, "title_match_best"
    return None, "ambiguous_or_low_similarity"


def acl_anthology_detect_accepted_publication(title=None, doi=None, year=None):
    result = acl_anthology_publication_search(title=title, doi=doi, year=year)
    hit, reason = choose_acl_anthology_hit(result, title=title, doi=doi, year=year)
    if not hit:
        return {
            "status": "acl_anthology_not_found_or_ambiguous",
            "venue_name": None,
            "venue_type": "auto",
            "acronym": "",
            "evidence_source": f"ACL Anthology local metadata: {reason}",
            "interface_version": "accepted-publication-v1",
            "acl_anthology": {"query": result.get("query"), "status": result.get("status"), "reason": reason, "top_hits": (result.get("hits") or [])[:3]},
        }
    venue_id = norm(hit.get("venue_id"))
    venue_name = hit.get("venue_name") or hit.get("venue_acronym") or hit.get("volume_title")
    venue_type = "journal" if venue_id in {"tacl", "cl"} else "conference"
    return {
        "status": "acl_anthology_confirmed",
        "venue_name": venue_name,
        "venue_type": venue_type,
        "acronym": hit.get("venue_acronym") or "",
        "evidence_source": f"ACL Anthology local metadata: {reason}",
        "interface_version": "accepted-publication-v1",
        "acl_anthology": hit,
    }


def dblp_publication_search(title=None, doi=None, authors=None, year=None, limit=10):
    """Search DBLP publication API and return normalized hit info.

    DBLP search API docs: https://dblp.uni-trier.de/faq/How+to+use+the+dblp+search+API.html
    Endpoint used: https://dblp.org/search/publ/api?q=...&format=json&h=...&c=0
    """
    query_parts = []
    if title: query_parts.append(title)
    if authors:
        if isinstance(authors, str): query_parts.append(authors)
        else: query_parts.extend(str(a) for a in authors[:4])
    if year: query_parts.append(str(year))
    if not query_parts and doi: query_parts.append(doi)
    if not query_parts: return {"status": "missing_query", "hits": []}
    data = get_json("https://dblp.org/search/publ/api", {"q": " ".join(query_parts), "format": "json", "h": min(max(limit, 1), 1000), "c": 0})
    if not isinstance(data, dict) or data.get("_error"):
        return {"status": "api_error", "error": (data or {}).get("_error") if isinstance(data, dict) else str(data), "hits": []}
    raw_hits = (((data.get("result") or {}).get("hits") or {}).get("hit") or [])
    hits = []
    for h in as_list(raw_hits):
        info = h.get("info") or {}
        hit_title = unescape(clean_cell(info.get("title"))).rstrip(".")
        sim = title_similarity(title, hit_title) if title else 0.0
        doi_match = bool(doi and norm(info.get("doi")) == norm(doi))
        year_match = bool(year and clean_cell(info.get("year")) == str(year))
        hits.append({
            "score": int(h.get("@score", 0) or 0),
            "title": hit_title,
            "title_similarity": round(sim, 4),
            "venue": clean_cell(info.get("venue")),
            "year": clean_cell(info.get("year")),
            "type": clean_cell(info.get("type")),
            "key": clean_cell(info.get("key")),
            "doi": clean_cell(info.get("doi")),
            "ee": clean_cell(info.get("ee")),
            "url": clean_cell(info.get("url")),
            "doi_match": doi_match,
            "year_match": year_match,
            "raw": info,
        })
    hits.sort(key=lambda x: (x["doi_match"], x["title_similarity"], x["year_match"], x["score"]), reverse=True)
    return {"status": "ok", "query": " ".join(query_parts), "hits": hits, "total": clean_cell(((data.get("result") or {}).get("hits") or {}).get("@total"))}


def choose_dblp_hit(search_result, title=None, doi=None, year=None, min_title_similarity=0.88):
    hits = (search_result or {}).get("hits") or []
    if not hits: return None, "no_dblp_hit"
    for h in hits:
        if h.get("doi_match"):
            return h, "doi_match"
    for h in hits:
        if title and h.get("title_similarity", 0) >= min_title_similarity and (not year or h.get("year_match")):
            return h, "title_year_match" if year else "title_match"
    best = hits[0]
    if title and best.get("title_similarity", 0) >= min_title_similarity:
        return best, "title_match_best"
    return None, "ambiguous_or_low_similarity"


def venue_type_from_dblp_hit(hit):
    typ = norm((hit or {}).get("type"))
    key = clean_cell((hit or {}).get("key"))
    venue = clean_cell((hit or {}).get("venue"))
    if key.startswith("conf/") or any(k in typ for k in ["conference", "workshop", "proceedings"]):
        return "conference"
    if key.startswith("journals/") or "journal" in typ:
        # DBLP stores CoRR/arXiv under journals/corr; treat it as not a confirmed journal venue.
        if norm(venue) in {"corr", "arxiv"} or key.startswith("journals/corr/"):
            return "preprint"
        return "journal"
    return "auto"


def dblp_detect_accepted_publication(title=None, doi=None, year=None, authors=None):
    result = dblp_publication_search(title=title, doi=doi, authors=authors, year=year)
    hit, reason = choose_dblp_hit(result, title=title, doi=doi, year=year)
    if not hit:
        return {
            "status": "dblp_not_found_or_ambiguous",
            "venue_name": None,
            "venue_type": "auto",
            "acronym": "",
            "evidence_source": f"dblp publication search: {reason}",
            "interface_version": "accepted-publication-v1",
            "dblp": {"query": result.get("query"), "status": result.get("status"), "reason": reason, "top_hits": [{k:v for k,v in h.items() if k != "raw"} for h in (result.get("hits") or [])[:3]]},
        }
    vtype = venue_type_from_dblp_hit(hit)
    status = "dblp_confirmed" if vtype in {"conference", "journal"} else "dblp_preprint_or_unclassified"
    return {
        "status": status,
        "venue_name": hit.get("venue") or None,
        "venue_type": vtype,
        "acronym": hit.get("venue") or "",
        "evidence_source": f"dblp publication search: {reason}",
        "interface_version": "accepted-publication-v1",
        "dblp": {k: v for k, v in hit.items() if k != "raw"},
    }


_CONFIRMED_ACCEPTANCE_STATUSES = {
    "user_provided_confirmed",
    "openreview_confirmed",
    "acl_anthology_confirmed",
    "dblp_confirmed",
    "crossref_confirmed",
}


_NON_MAIN_TRACK_WARNINGS = {
    "workshop_or_colocated_event",
    "findings_or_non_main_track",
    "short_paper",
    "demo_paper",
    "poster_or_extended_abstract",
    "extended_abstract",
    "companion_proceedings",
}


def non_main_track(title, venue):
    text = norm((title or "") + " " + (venue or ""))
    checks = [("workshop", "workshop_or_colocated_event"), ("findings", "findings_or_non_main_track"), ("short paper", "short_paper"), ("demo", "demo_paper"), ("poster", "poster_or_extended_abstract"), ("extended abstract", "extended_abstract"), ("companion", "companion_proceedings")]
    return sorted({w for pat, w in checks if pat in text})


def is_acl_anthology_findings(accepted: Optional[dict[str, Any]]) -> bool:
    accepted = accepted or {}
    if clean_cell(accepted.get("status")) != "acl_anthology_confirmed":
        return False
    hit = accepted.get("acl_anthology") or {}
    text = norm(" ".join(clean_cell(x) for x in [
        accepted.get("venue_name"),
        accepted.get("acronym"),
        hit.get("venue_id"),
        hit.get("venue_acronym"),
        hit.get("venue_name"),
        hit.get("volume_title"),
        hit.get("anthology_id"),
    ]))
    return "findings" in text


def acl_anthology_findings_parent_acronym(accepted: Optional[dict[str, Any]]) -> str:
    if not is_acl_anthology_findings(accepted):
        return ""
    accepted = accepted or {}
    hit = accepted.get("acl_anthology") or {}
    raw_text = " ".join(clean_cell(x) for x in [
        accepted.get("venue_name"),
        accepted.get("acronym"),
        hit.get("venue_id"),
        hit.get("venue_acronym"),
        hit.get("venue_name"),
        hit.get("volume_title"),
        hit.get("anthology_id"),
        hit.get("source_xml"),
    ])
    upper = raw_text.upper()
    lowered = norm(raw_text)
    ordered_patterns = [
        ("EMNLP", [r"\bEMNLP\b", "empirical methods in natural language processing"]),
        ("NAACL", [r"\bNAACL\b", "north american chapter"]),
        ("EACL", [r"\bEACL\b", "european chapter"]),
        ("AACL", [r"\bAACL\b", "asia-pacific chapter", "asia pacific chapter"]),
        ("COLING", [r"\bCOLING\b", "international conference on computational linguistics"]),
        ("CoNLL", [r"\bCONLL\b", "computational natural language learning"]),
        ("ACL", [r"\bACL\b", "annual meeting of the association for computational linguistics", "association for computational linguistics"]),
    ]
    for acronym, patterns in ordered_patterns:
        for pattern in patterns:
            if pattern.startswith(r"\b"):
                if re.search(pattern, upper):
                    return acronym
            elif pattern in lowered:
                return acronym
    return ""


def clean_cell(x: Any) -> str:
    if x is None: return ""
    s = str(x).strip()
    return "" if s.lower() == "nan" else s


def norm_acronym(s: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]+", "", (s or "").upper())


def rank_known(value: Optional[str]) -> bool:
    v = clean_cell(value).lower()
    return bool(v) and v not in {"unknown", "unranked", "nan"}


def ranking_source_label(path: Path) -> str:
    return f"local ranking snapshot: {path}"


def detect_accepted_publication(doi=None, title=None, year=None, accepted_venue=None, accepted_type=None, accepted_acronym=None, metadata_source=None, authors=None, cr=None, use_openreview=True, openreview_venue_id=None, use_acl_anthology=True, use_dblp=True, use_crossref=True):
    """Compatibility interface for accepted-venue detection.

    Explicit user-provided accepted venue is highest-trust. Otherwise ACL
    Anthology is tried first for ACL/EMNLP/NAACL/EACL/AACL/TACL-style NLP
    publications, then DBLP for broader CS papers. Later this can be extended
    with Crossref/OpenAlex proceedings pages, publisher pages, or conference
    accepted-paper lists without changing downstream rank lookup.
    """
    if accepted_venue:
        return {
            "status": "user_provided_confirmed",
            "venue_name": clean_cell(accepted_venue),
            "venue_type": clean_cell(accepted_type or "auto"),
            "acronym": clean_cell(accepted_acronym),
            "evidence_source": "user_provided_accepted_venue",
            "interface_version": "accepted-publication-v1",
        }
    if use_openreview and title and (openreview_venue_id or os.getenv("OPENREVIEW_VENUE_IDS")):
        openreview_result = openreview_detect_accepted_publication(title=title, year=year, venue_id=openreview_venue_id)
        if openreview_result.get("status") in {"openreview_confirmed", "openreview_not_accepted"}:
            return openreview_result
    if use_acl_anthology and (title or doi):
        acl = acl_anthology_detect_accepted_publication(title=title, doi=doi, year=year)
        if acl.get("status") == "acl_anthology_confirmed":
            return acl
    if use_dblp and title:
        dblp = dblp_detect_accepted_publication(title=title, doi=doi, year=year, authors=authors)
        if dblp.get("status") == "dblp_confirmed":
            return dblp
        if dblp.get("status") == "dblp_preprint_or_unclassified":
            return dblp
    if use_crossref and (doi or title):
        crossref_result = crossref_detect_accepted_publication(doi=doi, title=title, year=year, cr=cr)
        if crossref_result.get("status") == "crossref_confirmed":
            return crossref_result
        if crossref_result.get("status") == "crossref_preprint_or_unclassified":
            return crossref_result
    if metadata_source:
        return {
            "status": "metadata_inferred_unconfirmed",
            "venue_name": clean_cell(metadata_source),
            "venue_type": clean_cell(accepted_type or "auto"),
            "acronym": clean_cell(accepted_acronym),
            "evidence_source": "open_metadata_source_name; acceptance not independently verified",
            "interface_version": "accepted-publication-v1",
        }
    return {
        "status": "not_implemented_missing_accepted_venue",
        "venue_name": None,
        "venue_type": clean_cell(accepted_type or "auto"),
        "acronym": clean_cell(accepted_acronym),
        "evidence_source": "accepted venue detection hook reserved; DBLP did not provide a confirmed match; provide --accepted-venue for confirmed lookup",
        "interface_version": "accepted-publication-v1",
    }


def match_conference_ranking(name=None, acronym=None, rows=None):
    rows = rows if rows is not None else load_ranking_csv(conference_ranking_csv())
    qn = norm(name); qa = norm_acronym(acronym)
    if not qn and not qa:
        return None, ["missing_accepted_conference_name"]
    candidates = []
    for r in rows:
        rn = norm(r.get("会议名称") or r.get("canonical_name") or r.get("Title") or r.get("title"))
        ra = norm_acronym(r.get("简称") or r.get("alias") or r.get("Acronym") or r.get("acronym"))
        ralias = norm(r.get("CORE名称别名"))
        if qn and (qn == rn or qn == ralias):
            candidates.append(("title_exact", r)); continue
        if qa and qa == ra:
            candidates.append(("acronym_exact", r)); continue
        if qn and rn and (qn in rn or rn in qn):
            candidates.append(("title_contains", r))
    if not candidates and qn:
        keyed = [(norm(r.get("会议名称") or r.get("canonical_name") or r.get("Title") or r.get("title")), r) for r in rows]
        close = difflib.get_close_matches(qn, [k for k, _ in keyed if k], n=1, cutoff=0.90)
        if close:
            candidates.append(("title_fuzzy", next(r for k, r in keyed if k == close[0])))
    if not candidates:
        return {"name": name, "normalized_name": None, "type": "conference", "ccf_rank": "unknown", "core_rank": "unknown", "is_main_track_full_paper": None, "evidence_source": ranking_source_label(conference_ranking_csv()), "notes": "not found in conference_ranking.csv"}, ["accepted_conference_not_found_in_local_ranking"]
    method, r = candidates[0]
    ccf_rank = clean_cell(r.get("CCF等级") or r.get("ccf_rank")) or "unknown"
    core_rank = clean_cell(r.get("CORE等级") or r.get("core_rank")) or "unknown"
    non_main_warnings = non_main_track("", name or "")
    notes = []
    if clean_cell(r.get("匹配依据")): notes.append("csv_match_basis=" + clean_cell(r.get("匹配依据")))
    if clean_cell(r.get("CORE名称别名")): notes.append("core_alias=" + clean_cell(r.get("CORE名称别名")))
    if clean_cell(r.get("数据来源")): notes.append("sources=" + clean_cell(r.get("数据来源")))
    return {
        "name": name or clean_cell(r.get("会议名称")),
        "normalized_name": clean_cell(r.get("会议名称") or r.get("canonical_name") or name),
        "type": "conference",
        "ccf_rank": ccf_rank,
        "core_rank": core_rank,
        "is_main_track_full_paper": False if non_main_warnings else None,
        "evidence_source": ranking_source_label(conference_ranking_csv()),
        "notes": "; ".join([f"lookup_match={method}"] + notes),
    }, non_main_warnings


def ranking_cell(row, *keys):
    for key in keys:
        val = clean_cell(row.get(key))
        if val:
            return val
    return None


def parse_float_cell(value):
    value = clean_cell(value)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def match_journal_ranking(name=None, acronym=None, rows=None):
    rows = rows if rows is not None else load_ranking_csv(journal_ranking_csv())
    qn = norm(name); qa = norm_acronym(acronym)
    if not qn and not qa:
        return None, ["missing_accepted_journal_name"]
    candidates = []
    for r in rows:
        rn = norm(r.get("期刊名称") or r.get("canonical_name") or r.get("Journal"))
        ra = norm_acronym(r.get("简称") or r.get("alias"))
        if qn and qn == rn:
            candidates.append(("title_exact", r)); continue
        if qa and qa == ra:
            candidates.append(("acronym_exact", r)); continue
    if not candidates and qn:
        keyed = [(norm(r.get("期刊名称") or r.get("canonical_name") or r.get("Journal")), r) for r in rows]
        close = difflib.get_close_matches(qn, [k for k, _ in keyed if k], n=1, cutoff=0.92)
        if close:
            candidates.append(("title_fuzzy", next(r for k, r in keyed if k == close[0])))
    if not candidates:
        return {"name": name, "issn": None, "ccf_rank": "unknown", "cas_quartile": "unknown", "jcr_quartile": "unknown", "impact_factor": None, "sjr": None, "openalex_summary_stats": None, "evidence_source": ranking_source_label(journal_ranking_csv()) + "; not found in journal_ranking.csv"}, ["accepted_journal_not_found_in_local_ranking"]
    method, r = candidates[0]
    notes = []
    note_aliases = [
        ("CCF领域", ["CCF领域"]),
        ("中科院大类", ["中科院大类", "JCR大类"]),
        ("中科院 Top", ["中科院 Top", "JCR Top"]),
        ("WOS索引", ["WOS索引"]),
        ("中科院小类分区", ["中科院小类分区", "JCR小类分区"]),
        ("JCR类别", ["JCR类别", "Category"]),
        ("JCR分区2024", ["JCR分区2024", "IF Quartile(2024)"]),
        ("JCR影响因子2024", ["JCR影响因子2024", "IF(2024)"]),
        ("特殊标注", ["特殊标注"]),
        ("数据来源", ["数据来源"]),
    ]
    for label, keys in note_aliases:
        val = ranking_cell(r, *keys)
        if val: notes.append(f"{label}={val}")
    return {
        "name": clean_cell(r.get("期刊名称") or name),
        "issn": None,
        "ccf_rank": clean_cell(r.get("CCF等级")) or "unknown",
        "cas_quartile": ranking_cell(r, "中科院大类分区", "JCR大类分区") or "unknown",
        "jcr_quartile": ranking_cell(r, "JCR分区2024", "IF Quartile(2024)") or "unknown",
        "impact_factor": parse_float_cell(ranking_cell(r, "JCR影响因子2024", "IF(2024)")),
        "sjr": None,
        "openalex_summary_stats": None,
        "evidence_source": ranking_source_label(journal_ranking_csv()) + f"; lookup_match={method}; " + "; ".join(notes),
    }, []


def match_venue(name, title, rows):
    if not name: return None, ["missing_venue_name"]
    q = norm(name); cand = []
    for r in rows:
        keys = [norm(r.get("alias")), norm(r.get("canonical_name"))]
        if q in keys or any(k and k in q for k in keys): cand.append(r)
    if not cand:
        keyed = [(norm(r.get("alias") or r.get("canonical_name")), r) for r in rows]
        close = difflib.get_close_matches(q, [x[0] for x in keyed], n=1, cutoff=0.86)
        if close: cand.append(next(r for k, r in keyed if k == close[0]))
    if not cand:
        return {"name": name, "normalized_name": None, "type": "unknown", "ccf_rank": "unknown", "core_rank": "unknown", "is_main_track_full_paper": None, "evidence_source": "no local match", "notes": "not found"}, ["venue_not_found_in_local_registry"]
    r = cand[0]; warns = non_main_track(title, name)
    is_main = str(r.get("main_track_only","")).lower() == "true" and r.get("kind") != "workshop" and not warns
    return {"name": name, "normalized_name": r.get("canonical_name") or name, "type": r.get("kind") or "unknown", "ccf_rank": r.get("ccf_rank") or "unknown", "core_rank": r.get("core_rank") or "unknown", "is_main_track_full_paper": is_main, "evidence_source": "local registry: " + (r.get("snapshot") or ""), "notes": r.get("notes","")}, warns

def match_journal(name, oa, rows):
    if not name: return None
    src = ((oa or {}).get("primary_location") or {}).get("source") or {}
    issns = set(src.get("issn") or [])
    if src.get("issn_l"): issns.add(src["issn_l"])
    for r in rows:
        if ({r.get("issn",""), r.get("issn_l","")} - {""}) & issns or norm(r.get("canonical_name")) == norm(name):
            return {"name": r.get("canonical_name") or name, "issn": r.get("issn_l") or r.get("issn"), "ccf_rank": r.get("ccf_rank") or "unknown", "cas_quartile": r.get("cas_quartile") or None, "jcr_quartile": r.get("jcr_quartile") or None, "impact_factor": parse_float_cell(r.get("impact_factor")), "sjr": None, "openalex_summary_stats": None, "evidence_source": r.get("source") or "local journal registry"}
    if src:
        return {"name": src.get("display_name") or name, "issn": src.get("issn_l"), "ccf_rank": "unknown", "cas_quartile": None, "jcr_quartile": None, "impact_factor": None, "sjr": None, "openalex_summary_stats": src.get("summary_stats"), "evidence_source": "openalex source metadata"}
    return None

def retraction_status(oa, cr):
    checked, updates, flag = [], [], None
    if oa and not oa.get("_error"):
        checked.append("openalex"); flag = bool(oa.get("is_retracted"))
    if cr and not cr.get("_error"):
        checked.append("crossref")
        for u in cr.get("update-to", []) or []:
            updates.append(u)
            if "retraction" in norm(json.dumps(u)): flag = True
        if "retract" in norm(json.dumps(cr.get("relation") or {})): flag = True
    return flag, updates, checked

def classify(card):
    warnings = list(card["warnings"]); flags = []
    if card["publication_status"].get("is_retracted"): return "do_not_use", ["retracted"], warnings
    c = card["citations"]; vals = [x for x in [c.get("openalex"), c.get("semantic_scholar"), c.get("crossref")] if isinstance(x, int)]
    if c.get("openalex") is not None and c.get("semantic_scholar") is not None: flags.append("citation_count_cross_checked")
    elif vals: flags.append("single_citation_source")
    else: warnings.append("missing_open_citation_counts")
    if c.get("openalex") is not None and c.get("semantic_scholar") is not None:
        a,b = c["openalex"], c["semantic_scholar"]
        if max(a,b) >= 20 and (max(a,b)+1)/(min(a,b)+1) > 2 and abs(a-b) > 20:
            warnings.append("large_citation_count_discrepancy_openalex_vs_semantic_scholar")
    v, j = card.get("venue"), card.get("journal")
    accepted = card.get("accepted_publication") or {}
    accepted_status = clean_cell(accepted.get("status"))
    acceptance_unconfirmed = accepted_status not in _CONFIRMED_ACCEPTANCE_STATUSES
    if acceptance_unconfirmed:
        warnings.append("accepted_publication_not_independently_confirmed")
    if is_acl_anthology_findings(accepted):
        warnings = [w for w in warnings if w != "findings_or_non_main_track"]
        flags.append("acl_anthology_findings_confirmed")
    top = False
    if v:
        non_main = v.get("is_main_track_full_paper") is False or any(w in warnings for w in _NON_MAIN_TRACK_WARNINGS)
        if non_main:
            warnings.append("not_main_track_full_paper")
        if not non_main and not acceptance_unconfirmed and (v.get("ccf_rank") == "A" or v.get("core_rank") == "A*"):
            flags.append("top_venue"); top = True
    if j and not acceptance_unconfirmed and (j.get("ccf_rank") == "A" or j.get("cas_quartile") in {"1区", "Q1"} or j.get("jcr_quartile") == "Q1"): flags.append("high_quality_journal_proxy"); top = True
    year = card["paper"].get("year"); recent = isinstance(year, int) and year >= dt.date.today().year - 1
    m = max(vals or [0])
    if recent and m < 20: flags.append("recent_paper_low_citation_not_penalized")
    elif m >= 100: flags.append("highly_cited")
    elif m >= 20: flags.append("moderately_cited")
    else: warnings.append("low_citation_for_non_recent_paper")
    if top and "not_main_track_full_paper" not in warnings: return "strong_evidence", sorted(set(flags)), sorted(set(warnings))
    if "moderately_cited" in flags or "highly_cited" in flags: return "supporting_evidence", sorted(set(flags)), sorted(set(warnings))
    if any(w in warnings for w in ["venue_not_found_in_local_registry","missing_venue_name"]): return "needs_human_review", sorted(set(flags)), sorted(set(warnings))
    return "weak_or_contextual_evidence", sorted(set(flags)), sorted(set(warnings))

def build_card(doi=None, title=None, year=None, arxiv_url=None, include_raw=False, accepted_venue=None, accepted_type=None, accepted_acronym=None, use_openreview=True, openreview_venue_id=None, use_acl_anthology=True, use_dblp=True, use_crossref=True):
    arxiv_id = arxiv_id_from_url(arxiv_url)
    arxiv_doi = arxiv_doi_from_id(arxiv_id) if arxiv_id else None
    query_doi = doi or arxiv_doi
    oa = openalex(query_doi) if query_doi else None
    if (not oa or oa.get("_error")) and title:
        oa = choose_openalex_work(openalex_title_search(title=title, year=year), title=title, year=year)
    if doi:
        ss = semantic_scholar(doi)
    elif arxiv_id:
        ss = semantic_scholar_arxiv(arxiv_id)
    else:
        ss = None
    cr = crossref(query_doi) if query_doi else None
    t = title_from(oa, ss, cr, title); y = year_from(oa, ss, cr, year); src = source_name(oa, ss, cr)
    typ = (oa or {}).get("type") or (cr or {}).get("type")
    warnings = non_main_track(t, src)
    pubtext = norm((typ or "") + " " + (src or "") + " " + (arxiv_url or ""))
    accepted = detect_accepted_publication(doi=doi, title=t, year=y, accepted_venue=accepted_venue, accepted_type=accepted_type, accepted_acronym=accepted_acronym, metadata_source=src, cr=cr, use_openreview=use_openreview, openreview_venue_id=openreview_venue_id, use_acl_anthology=use_acl_anthology, use_dblp=use_dblp, use_crossref=use_crossref)
    venue = journal = None
    accepted_name = accepted.get("venue_name")
    accepted_kind = norm(accepted.get("venue_type"))
    accepted_acro = accepted.get("acronym")
    ranking_name = accepted_name
    ranking_acro = accepted_acro
    acl_findings_parent_acro = acl_anthology_findings_parent_acronym(accepted)
    if acl_findings_parent_acro:
        ranking_name = None
        ranking_acro = acl_findings_parent_acro
    if accepted.get("status") == "not_implemented_missing_accepted_venue":
        warnings.append("accepted_publication_detection_not_implemented")
    if accepted.get("status") == "dblp_not_found_or_ambiguous":
        warnings.append("dblp_acceptance_detection_not_found_or_ambiguous")
    if accepted.get("status") == "dblp_preprint_or_unclassified":
        warnings.append("dblp_match_is_preprint_or_unclassified_not_confirmed_venue")
    if accepted.get("status") == "acl_anthology_not_found_or_ambiguous":
        warnings.append("acl_anthology_detection_not_found_or_ambiguous")
    if accepted.get("status") == "openreview_not_found_or_ambiguous":
        warnings.append("openreview_detection_not_found_or_ambiguous")
    if accepted.get("status") == "openreview_not_accepted":
        warnings.append("openreview_match_not_accepted")
    if accepted.get("status") == "crossref_not_found_or_ambiguous":
        warnings.append("crossref_acceptance_detection_not_found_or_ambiguous")
    if accepted.get("status") == "crossref_preprint_or_unclassified":
        warnings.append("crossref_match_is_preprint_or_unclassified_not_confirmed_venue")
    if accepted.get("acl_anthology"):
        warnings += non_main_track(t, accepted["acl_anthology"].get("volume_title"))
    if accepted_name:
        if accepted_kind == "preprint":
            warnings.append("accepted_publication_is_preprint_not_ranked_as_venue")
        elif accepted_kind in {"conference", "venue", "proceedings", "symposium"} or (accepted_kind == "auto" and any(k in pubtext for k in ["proceedings","conference","workshop","symposium"])):
            venue, ws = match_conference_ranking(ranking_name, ranking_acro); warnings += ws
            if venue and acl_findings_parent_acro:
                venue["notes"] = "; ".join(x for x in [venue.get("notes"), f"acl_anthology_findings_parent={acl_findings_parent_acro}"] if x)
        elif accepted_kind in {"journal", "source"}:
            journal, ws = match_journal_ranking(ranking_name, ranking_acro); warnings += ws
        else:
            # Auto mode: try journal and conference snapshots; prefer known ranks, otherwise keep the better match.
            j, jw = match_journal_ranking(ranking_name, ranking_acro)
            v, vw = match_conference_ranking(ranking_name, ranking_acro)
            if v and acl_findings_parent_acro:
                v["notes"] = "; ".join(x for x in [v.get("notes"), f"acl_anthology_findings_parent={acl_findings_parent_acro}"] if x)
            j_known = bool(j) and (rank_known(j.get("ccf_rank")) or rank_known(j.get("cas_quartile")) or rank_known(j.get("jcr_quartile")))
            v_known = bool(v) and (rank_known(v.get("ccf_rank")) or rank_known(v.get("core_rank")))
            if v_known and not j_known:
                venue = v; warnings += vw
            elif j_known and not v_known:
                journal = j; warnings += jw
            elif any(k in pubtext for k in ["proceedings","conference","workshop","symposium"]):
                venue = v; warnings += vw
            else:
                journal = j; warnings += jw
    else:
        warnings.append("accepted_venue_missing_rank_lookup_skipped")
    is_ret, updates, checked = retraction_status(oa, cr)
    preprint_evidence = any(k in pubtext for k in ["arxiv","preprint","posted content","biorxiv","medrxiv"])
    accepted_confirmed = accepted.get("status") in {"user_provided_confirmed", "openreview_confirmed", "acl_anthology_confirmed", "dblp_confirmed", "crossref_confirmed"} and norm(accepted.get("venue_type")) in {"conference", "journal"}
    preprint = bool(preprint_evidence and not accepted_confirmed)
    citations = {"openalex": None, "semantic_scholar": None, "semantic_scholar_influential": None, "crossref": None, "google_scholar_manual": None, "counts_by_year": [], "checked_at": today()}
    if oa and not oa.get("_error"): citations["openalex"] = oa.get("cited_by_count"); citations["counts_by_year"] = oa.get("counts_by_year") or []
    if ss and not ss.get("_error"): citations["semantic_scholar"] = ss.get("citationCount"); citations["semantic_scholar_influential"] = ss.get("influentialCitationCount")
    if cr and not cr.get("_error"): citations["crossref"] = cr.get("is-referenced-by-count")
    if citations["crossref"] is None and (accepted.get("crossref") or {}).get("is_referenced_by_count") is not None:
        citations["crossref"] = accepted["crossref"].get("is_referenced_by_count")
    for name, obj in [("openalex", oa), ("semantic_scholar", ss), ("crossref", cr)]:
        if obj and obj.get("_error"): warnings.append(f"{name}_error:{obj['_error']}")
    authors = [a.get("name") for a in (ss or {}).get("authors", []) if isinstance(a, dict) and a.get("name")] if ss and not ss.get("_error") else []
    source_ids = {}
    if arxiv_url: source_ids["arxiv_url"] = clean_cell(arxiv_url)
    if arxiv_id: source_ids["arxiv_id"] = arxiv_id
    if arxiv_doi: source_ids["arxiv_doi"] = arxiv_doi
    publication_status = {"is_retracted": is_ret, "is_preprint_only": preprint, "status": "preprint_unconfirmed" if preprint else ("accepted_publication_confirmed" if accepted_confirmed else "publication_unclassified"), "has_expression_of_concern": any("expression" in norm(json.dumps(u)) and "concern" in norm(json.dumps(u)) for u in updates), "updates": updates, "sources_checked": checked}
    card = {"paper": {"title": t, "doi": doi, "year": y, "authors": authors, "type": typ, "source_ids": source_ids}, "citations": citations, "venue": venue, "journal": journal, "accepted_publication": accepted, "publication_status": publication_status, "tier": "needs_human_review", "quality_flags": [], "warnings": sorted(set(warnings)), "raw_sources": {}, "checked_at": today()}
    tier, flags, warns = classify(card); card["tier"] = tier; card["quality_flags"] = flags; card["warnings"] = warns
    if include_raw: card["raw_sources"] = {"openalex": oa, "semantic_scholar": ss, "crossref": cr}
    return card

def rows_from_input(path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"): yield line

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doi"); ap.add_argument("--title"); ap.add_argument("--year", type=int); ap.add_argument("--arxiv-url", help="Optional arXiv URL/abs link; title is still used for accepted-venue detection")
    ap.add_argument("--accepted-venue", help="Confirmed venue/journal name when acceptance has already been verified externally")
    ap.add_argument("--accepted-type", choices=["auto", "conference", "journal"], default="auto", help="Type of --accepted-venue; auto tries both ranking tables")
    ap.add_argument("--accepted-acronym", help="Optional confirmed acronym such as AAAI, CCS, TOCS")
    ap.add_argument("--openreview-venue-id", help="OpenReview venue id to query, e.g. ICLR.cc/2024/Conference")
    ap.add_argument("--no-openreview", action="store_true", help="Disable OpenReview accepted-submission detection")
    ap.add_argument("--no-acl-anthology", action="store_true", help="Disable ACL Anthology local metadata acceptance detection")
    ap.add_argument("--no-dblp", action="store_true", help="Disable DBLP publication search acceptance detection")
    ap.add_argument("--no-crossref", action="store_true", help="Disable Crossref Works API accepted journal/proceedings fallback detection")
    ap.add_argument("--input"); ap.add_argument("--out"); ap.add_argument("--include-raw", action="store_true")
    a = ap.parse_args()
    if a.input:
        if not a.out: ap.error("--out is required with --input")
        with open(a.out, "w", encoding="utf-8") as f:
            for doi in rows_from_input(a.input):
                f.write(json.dumps(build_card(doi=doi, include_raw=a.include_raw, accepted_venue=a.accepted_venue, accepted_type=a.accepted_type, accepted_acronym=a.accepted_acronym, use_openreview=not a.no_openreview, openreview_venue_id=a.openreview_venue_id, use_acl_anthology=not a.no_acl_anthology, use_dblp=not a.no_dblp, use_crossref=not a.no_crossref), ensure_ascii=False) + "\n")
        return
    if not a.doi and not a.title: ap.error("provide --doi, --title, or --input")
    card = build_card(a.doi, a.title, a.year, arxiv_url=a.arxiv_url, include_raw=a.include_raw, accepted_venue=a.accepted_venue, accepted_type=a.accepted_type, accepted_acronym=a.accepted_acronym, use_openreview=not a.no_openreview, openreview_venue_id=a.openreview_venue_id, use_acl_anthology=not a.no_acl_anthology, use_dblp=not a.no_dblp, use_crossref=not a.no_crossref)
    s = json.dumps(card, ensure_ascii=False, indent=2)
    if a.out: Path(a.out).write_text(s + "\n", encoding="utf-8")
    else: print(s)

if __name__ == "__main__": main()
