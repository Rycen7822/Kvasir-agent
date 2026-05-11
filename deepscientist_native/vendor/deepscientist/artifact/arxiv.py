from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 6
USER_AGENT = "DeepScientist/0.1"
ARXIV_API_URL = "http://export.arxiv.org/api/query?id_list={paper_id}"
ARXIV_XML_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


@dataclass(frozen=True)
class _FetchPlan:
    name: str
    url: str
    content_mode: str
    parser: Callable[[str, str, str], dict[str, Any]]
    timeout: int = DEFAULT_TIMEOUT_SECONDS


class _HTMLTextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "caption",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "li":
            self._parts.append("\n- ")
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(unescape(text))

    def text(self) -> str:
        lines: list[str] = []
        for raw_line in "".join(self._parts).splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if line:
                lines.append(line)
            elif lines and lines[-1] != "":
                lines.append("")
        return "\n".join(lines).strip()


def read_arxiv_content(paper_id: str, *, full_text: bool = False) -> dict[str, Any]:
    normalized_id = normalize_arxiv_id(paper_id)
    if not normalized_id:
        return {
            "ok": False,
            "paper_id": str(paper_id or "").strip(),
            "requested_full_text": full_text,
            "error": "Invalid arXiv paper id.",
            "attempts": [],
            "guidance": "Pass an arXiv id like `2010.11929` or `2401.12345v2`.",
        }

    metadata = fetch_arxiv_metadata(normalized_id)
    attempts: list[dict[str, Any]] = list(metadata.get("attempts") or [])
    if not metadata.get("ok"):
        mode = "full text" if full_text else "overview"
        return {
            "ok": False,
            "paper_id": normalized_id,
            "requested_full_text": full_text,
            "error": f"Unable to fetch arXiv {mode} content for `{normalized_id}`.",
            "attempts": attempts,
            "guidance": "Use web search to confirm the paper id or try again later.",
        }

    merged: dict[str, Any] = {
        "ok": True,
        "paper_id": metadata.get("paper_id") or normalized_id,
        "requested_full_text": full_text,
        "title": metadata.get("title"),
        "authors": metadata.get("authors") or [],
        "categories": metadata.get("categories") or [],
        "abstract": metadata.get("abstract") or "",
        "published_at": metadata.get("published_at") or "",
        "version": metadata.get("version"),
        "primary_class": metadata.get("primary_class") or "",
        "bibtex": metadata.get("bibtex") or "",
        "metadata_source": metadata.get("metadata_source") or metadata.get("source"),
        "abs_url": metadata.get("abs_url") or f"https://arxiv.org/abs/{normalized_id}",
        "pdf_url": metadata.get("pdf_url") or f"https://arxiv.org/pdf/{normalized_id}.pdf",
    }

    if full_text:
        for plan in _full_text_plans(normalized_id):
            try:
                payload = _fetch_text(plan.url, timeout=plan.timeout)
                parsed = plan.parser(normalized_id, payload, plan.url)
                content = str(parsed.get("content") or "").strip()
                if not content:
                    attempts.append(
                        {
                            "source": plan.name,
                            "url": plan.url,
                            "ok": False,
                            "error": "Empty response.",
                        }
                    )
                    continue
                attempts.append(
                    {
                        "source": plan.name,
                        "url": plan.url,
                        "ok": True,
                        "content_mode": plan.content_mode,
                    }
                )
                return {
                    **merged,
                    "content_mode": plan.content_mode,
                    "source": plan.name,
                    "source_url": plan.url,
                    "summary_source": metadata.get("metadata_source") or metadata.get("source"),
                    "overview": "",
                    "overview_source": None,
                    "content": _build_full_text_content(merged, content),
                    "attempts": attempts,
                    "guidance": "Use web search for discovery. Use `artifact.arxiv(...)` after you already know the arXiv paper id.",
                }
            except Exception as exc:  # noqa: BLE001
                attempts.append(
                    {
                        "source": plan.name,
                        "url": plan.url,
                        "ok": False,
                        "error": _format_error(exc),
                    }
                )

        return {
            **merged,
            "content_mode": "abstract",
            "source": metadata.get("source"),
            "source_url": metadata.get("source_url"),
            "summary_source": metadata.get("metadata_source") or metadata.get("source"),
            "overview": "",
            "overview_source": None,
            "content": _build_overview_content(merged, None),
            "attempts": attempts,
            "guidance": "Use web search for discovery. Use `artifact.arxiv(...)` after you already know the arXiv paper id.",
        }

    overview_text = ""
    overview_markdown = ""
    overview_source: str | None = None
    overview_url: str | None = None
    for plan in _overview_plans(normalized_id):
        try:
            payload = _fetch_text(plan.url, timeout=plan.timeout)
            parsed = plan.parser(normalized_id, payload, plan.url)
            candidate = str(parsed.get("abstract") or parsed.get("content") or "").strip()
            candidate_markdown = str(parsed.get("overview_markdown") or parsed.get("content") or "").strip()
            if not candidate:
                attempts.append(
                    {
                        "source": plan.name,
                        "url": plan.url,
                        "ok": False,
                        "error": "Empty response.",
                    }
                )
                continue
            attempts.append(
                {
                    "source": plan.name,
                    "url": plan.url,
                    "ok": True,
                    "content_mode": "overview",
                }
            )
            overview_text = candidate
            overview_markdown = candidate_markdown
            overview_source = plan.name
            overview_url = plan.url
            break
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "source": plan.name,
                    "url": plan.url,
                    "ok": False,
                    "error": _format_error(exc),
                }
            )

    return {
        **merged,
        "content_mode": "overview" if overview_text else "abstract",
        "source": overview_source or metadata.get("source"),
        "source_url": overview_url or metadata.get("source_url"),
        "summary_source": overview_source or metadata.get("metadata_source") or metadata.get("source"),
        "overview": overview_text,
        "overview_markdown": overview_markdown,
        "overview_source": overview_source,
        "content": _build_overview_content(merged, overview_text or None),
        "attempts": attempts,
        "guidance": "Use web search for discovery. Use `artifact.arxiv(...)` after you already know the arXiv paper id.",
    }


def fetch_arxiv_metadata(paper_id: str) -> dict[str, Any]:
    normalized_id = normalize_arxiv_id(paper_id)
    if not normalized_id:
        return {
            "ok": False,
            "paper_id": str(paper_id or "").strip(),
            "error": "Invalid arXiv paper id.",
            "attempts": [],
        }

    attempts: list[dict[str, Any]] = []
    for plan in _metadata_plans(normalized_id):
        try:
            payload = _fetch_text(plan.url, timeout=plan.timeout)
            parsed = plan.parser(normalized_id, payload, plan.url)
            title = str(parsed.get("title") or "").strip()
            abstract = str(parsed.get("abstract") or "").strip()
            if not title and not abstract:
                attempts.append(
                    {
                        "source": plan.name,
                        "url": plan.url,
                        "ok": False,
                        "error": "Empty response.",
                    }
                )
                continue
            attempts.append(
                {
                    "source": plan.name,
                    "url": plan.url,
                    "ok": True,
                    "content_mode": plan.content_mode,
                }
            )
            canonical_id = str(parsed.get("paper_id") or normalized_id).strip() or normalized_id
            primary_class = str(parsed.get("primary_class") or "").strip()
            published_at = str(parsed.get("published_at") or "").strip()
            version = parsed.get("version")
            metadata = {
                "ok": True,
                "paper_id": canonical_id,
                "source": plan.name,
                "source_url": plan.url,
                "metadata_source": plan.name,
                "title": title or canonical_id,
                "authors": parsed.get("authors") or [],
                "categories": parsed.get("categories") or ([] if not primary_class else [primary_class]),
                "abstract": abstract,
                "published_at": published_at,
                "version": version if isinstance(version, int) else _parse_arxiv_version(canonical_id),
                "primary_class": primary_class or ((parsed.get("categories") or [None])[0] or ""),
                "abs_url": str(parsed.get("abs_url") or f"https://arxiv.org/abs/{canonical_id}"),
                "pdf_url": str(parsed.get("pdf_url") or f"https://arxiv.org/pdf/{canonical_id}.pdf"),
                "attempts": attempts,
            }
            metadata["bibtex"] = _build_bibtex(metadata)
            metadata["content"] = _build_metadata_content(metadata)
            return metadata
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "source": plan.name,
                    "url": plan.url,
                    "ok": False,
                    "error": _format_error(exc),
                }
            )

    return {
        "ok": False,
        "paper_id": normalized_id,
        "error": f"Unable to fetch arXiv metadata for `{normalized_id}`.",
        "attempts": attempts,
    }


def normalize_arxiv_id(raw_value: str) -> str | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    value = value.replace("https://", "").replace("http://", "")
    value = value.rstrip("/")
    value = value.removesuffix(".pdf").removesuffix(".md")
    patterns = (
        re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE),
        re.compile(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)", re.IGNORECASE),
    )
    for pattern in patterns:
        match = pattern.search(value)
        if match:
            return match.group(1)
    return None


def _overview_plans(paper_id: str) -> list[_FetchPlan]:
    return [
        _FetchPlan(
            name="alphaxiv_overview",
            url=f"https://www.alphaxiv.org/overview/{paper_id}.md",
            content_mode="overview",
            parser=_parse_markdown,
            timeout=4,
        ),
    ]


def _full_text_plans(paper_id: str) -> list[_FetchPlan]:
    return [
        _FetchPlan(
            name="alphaxiv_full_text",
            url=f"https://www.alphaxiv.org/abs/{paper_id}.md",
            content_mode="full_text",
            parser=_parse_markdown,
        ),
        _FetchPlan(
            name="arxiv_html",
            url=f"https://arxiv.org/html/{paper_id}",
            content_mode="full_text",
            parser=_parse_article_html,
        ),
        _FetchPlan(
            name="ar5iv_labs_html",
            url=f"https://ar5iv.labs.arxiv.org/html/{paper_id}",
            content_mode="full_text",
            parser=_parse_article_html,
        ),
        _FetchPlan(
            name="ar5iv_html",
            url=f"https://ar5iv.org/html/{paper_id}",
            content_mode="full_text",
            parser=_parse_article_html,
        ),
        _FetchPlan(
            name="arxiv_abstract",
            url=f"https://arxiv.org/abs/{paper_id}",
            content_mode="abstract",
            parser=_parse_arxiv_abstract_html,
        ),
    ]


def _metadata_plans(paper_id: str) -> list[_FetchPlan]:
    return [
        _FetchPlan(
            name="arxiv_api",
            url=ARXIV_API_URL.format(paper_id=paper_id),
            content_mode="abstract",
            parser=_parse_arxiv_atom,
            timeout=8,
        ),
        _FetchPlan(
            name="arxiv_abstract",
            url=f"https://arxiv.org/abs/{paper_id}",
            content_mode="abstract",
            parser=_parse_arxiv_abstract_html,
        ),
    ]


def _fetch_text(url: str, *, timeout: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/markdown,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _parse_markdown(paper_id: str, payload: str, url: str) -> dict[str, Any]:
    content = payload.lstrip("\ufeff").strip()
    if not content:
        return {"content": ""}
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else _first_nonempty_line(content)
    abstract = _markdown_to_text(content, title=title)
    return {
        "title": title,
        "authors": [],
        "categories": [],
        "abstract": abstract,
        "overview_markdown": content,
        "content": content,
    }


def _parse_arxiv_atom(paper_id: str, payload: str, url: str) -> dict[str, Any]:
    root = ET.fromstring(payload)
    entry = root.find("atom:entry", ARXIV_XML_NAMESPACES)
    if entry is None:
        return {"content": ""}

    title = _clean_inline_text(entry.findtext("atom:title", default="", namespaces=ARXIV_XML_NAMESPACES))
    abstract = _clean_inline_text(entry.findtext("atom:summary", default="", namespaces=ARXIV_XML_NAMESPACES))
    published_at = _clean_inline_text(
        entry.findtext("atom:published", default="", namespaces=ARXIV_XML_NAMESPACES)
    )
    authors: list[str] = []
    for author in entry.findall("atom:author", ARXIV_XML_NAMESPACES):
        author_name = _clean_inline_text(
            author.findtext("atom:name", default="", namespaces=ARXIV_XML_NAMESPACES)
        )
        if author_name:
            authors.append(author_name)

    categories: list[str] = []
    primary_class = ""
    primary_node = entry.find("arxiv:primary_category", ARXIV_XML_NAMESPACES)
    if primary_node is not None:
        primary_class = _clean_inline_text(primary_node.attrib.get("term", ""))
        if primary_class:
            categories.append(primary_class)
    for category in entry.findall("atom:category", ARXIV_XML_NAMESPACES):
        term = _clean_inline_text(category.attrib.get("term", ""))
        if term and term not in categories:
            categories.append(term)

    entry_id = _clean_inline_text(entry.findtext("atom:id", default="", namespaces=ARXIV_XML_NAMESPACES))
    entry_id_normalized = normalize_arxiv_id(entry_id) or paper_id
    canonical_id = normalize_arxiv_id(paper_id) or _strip_arxiv_version(entry_id_normalized) or paper_id
    version = _parse_arxiv_version(entry_id_normalized)
    abs_url = f"https://arxiv.org/abs/{canonical_id}"
    pdf_url = f"https://arxiv.org/pdf/{canonical_id}.pdf"
    return {
        "paper_id": canonical_id,
        "title": title,
        "authors": authors,
        "categories": categories,
        "primary_class": primary_class or (categories[0] if categories else ""),
        "published_at": _normalize_published_at(published_at),
        "version": version,
        "abstract": abstract,
        "abs_url": abs_url,
        "pdf_url": pdf_url,
        "content": _build_metadata_content(
            {
                "paper_id": canonical_id,
                "title": title,
                "authors": authors,
                "categories": categories,
                "primary_class": primary_class or (categories[0] if categories else ""),
                "published_at": _normalize_published_at(published_at),
                "version": version,
                "abstract": abstract,
                "abs_url": abs_url,
                "pdf_url": pdf_url,
            }
        ),
    }


def _parse_arxiv_abstract_html(paper_id: str, payload: str, url: str) -> dict[str, Any]:
    title = _match_first(payload, r'<meta name="citation_title" content="([^"]+)"')
    if not title:
        title = _match_first(payload, r"<title>(.*?)</title>", flags=re.IGNORECASE | re.DOTALL)
    authors = re.findall(r'<meta name="citation_author" content="([^"]+)"', payload)
    categories = _parse_arxiv_categories(payload)
    published_at = _normalize_published_at(_match_first(payload, r'<meta name="citation_date" content="([^"]+)"'))
    abstract = _match_first(
        payload,
        r'<span class="descriptor">Abstract:</span>(.*?)</blockquote>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    abstract = _clean_inline_text(abstract)
    if not abstract:
        abstract = _clean_inline_text(_extract_text(payload))
    primary_class = categories[0] if categories else ""
    metadata = {
        "paper_id": paper_id,
        "title": _clean_inline_text(title),
        "authors": [_clean_inline_text(author) for author in authors if _clean_inline_text(author)],
        "categories": categories,
        "abstract": abstract,
        "published_at": published_at,
        "version": _parse_arxiv_version(paper_id),
        "primary_class": primary_class,
        "abs_url": f"https://arxiv.org/abs/{paper_id}",
        "pdf_url": f"https://arxiv.org/pdf/{paper_id}.pdf",
    }
    return {
        **metadata,
        "content": _build_metadata_content(metadata),
    }


def _parse_article_html(paper_id: str, payload: str, url: str) -> dict[str, Any]:
    title = _match_first(payload, r"<title>(.*?)</title>", flags=re.IGNORECASE | re.DOTALL)
    article = _match_first(payload, r"<article[^>]*>(.*?)</article>", flags=re.IGNORECASE | re.DOTALL)
    body = article or _match_first(payload, r"<body[^>]*>(.*?)</body>", flags=re.IGNORECASE | re.DOTALL) or payload
    text = _extract_text(body)
    if not text:
        return {"content": ""}
    cleaned_title = _clean_inline_text(title)
    if cleaned_title:
        text = _trim_duplicate_title(text, cleaned_title)
    lines = []
    if cleaned_title:
        lines.extend([f"# {cleaned_title}", ""])
    lines.append(f"- paper_id: {paper_id}")
    lines.append(f"- source: {url}")
    lines.extend(["", text])
    return {
        "title": cleaned_title,
        "authors": [],
        "categories": [],
        "abstract": _summarize_text(text),
        "content": "\n".join(lines).strip(),
    }


def _extract_text(payload: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(payload)
    parser.close()
    return parser.text()


def _trim_duplicate_title(text: str, title: str) -> str:
    lines = [line for line in text.splitlines()]
    while lines and lines[0].strip().lower() == title.strip().lower():
        lines.pop(0)
    return "\n".join(lines).strip()


def _match_first(payload: str, pattern: str, *, flags: int = 0) -> str:
    match = re.search(pattern, payload, flags)
    if not match:
        return ""
    return unescape(match.group(1))


def _clean_inline_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return ""


def _markdown_to_text(content: str, *, title: str | None = None) -> str:
    text = re.sub(r"```.*?```", " ", content, flags=re.DOTALL)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    cleaned = _clean_inline_text(text)
    if title:
        title_prefix = _clean_inline_text(title)
        if cleaned.lower().startswith(title_prefix.lower()):
            cleaned = cleaned[len(title_prefix) :].strip(" :-")
    return _summarize_text(cleaned)


def _summarize_text(text: str, *, limit: int = 1600) -> str:
    cleaned = _clean_inline_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: max(0, limit - 1)].rstrip()}…"


def _parse_arxiv_categories(payload: str) -> list[str]:
    raw = _match_first(
        payload,
        r'<td class="tablecell subjects">(.*?)</td>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = _clean_inline_text(raw)
    if not cleaned:
        return []
    parts = [part.strip() for part in cleaned.split(";") if part.strip()]
    return parts


def _normalize_published_at(value: str) -> str:
    raw = _clean_inline_text(value)
    if not raw:
        return ""
    if "T" in raw:
        return raw.split("T", 1)[0]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    month_match = re.search(r"([A-Za-z]{3,9})\s+(\d{1,2}),\s*(\d{4})", raw)
    if month_match:
        month_lookup = {
            "jan": "01",
            "feb": "02",
            "mar": "03",
            "apr": "04",
            "may": "05",
            "jun": "06",
            "jul": "07",
            "aug": "08",
            "sep": "09",
            "oct": "10",
            "nov": "11",
            "dec": "12",
        }
        month = month_lookup.get(month_match.group(1)[:3].lower())
        if month:
            return f"{month_match.group(3)}-{month}-{int(month_match.group(2)):02d}"
    year_match = re.search(r"\b(\d{4})\b", raw)
    return year_match.group(1) if year_match else raw


def _parse_arxiv_version(paper_id: str) -> int | None:
    match = re.search(r"v(\d+)$", str(paper_id or "").strip(), re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _strip_arxiv_version(paper_id: str) -> str:
    return re.sub(r"v\d+$", "", str(paper_id or "").strip(), flags=re.IGNORECASE)


def _bibtex_year(published_at: str) -> str:
    match = re.search(r"\b(\d{4})\b", str(published_at or "").strip())
    return match.group(1) if match else ""


def _bibtex_key_author(authors: list[str]) -> str:
    if not authors:
        return "unknown"
    parts = re.split(r"[\s,]+", authors[0].strip())
    cleaned = [part for part in parts if part]
    if not cleaned:
        return "unknown"
    return re.sub(r"[^a-z0-9]+", "", cleaned[-1].lower()) or "unknown"


def _citation_key(paper_id: str, authors: list[str], published_at: str) -> str:
    year = _bibtex_year(published_at) or "0000"
    normalized_paper_id = re.sub(r"v\d+$", "", str(paper_id or "").lower())
    base_id = re.sub(r"[^a-z0-9]+", "", normalized_paper_id)
    if not base_id:
        base_id = "arxiv"
    return f"{_bibtex_key_author(authors)}{year}{base_id}"


def _build_bibtex(metadata: dict[str, Any]) -> str:
    paper_id = str(metadata.get("paper_id") or "").strip()
    title = str(metadata.get("title") or "").strip()
    authors = [str(item).strip() for item in (metadata.get("authors") or []) if str(item).strip()]
    published_at = str(metadata.get("published_at") or "").strip()
    primary_class = str(metadata.get("primary_class") or "").strip()
    year = _bibtex_year(published_at) or "0000"
    lines = [
        f"@misc{{{_citation_key(paper_id, authors, published_at)},",
        f"      title={{{title}}},",
        f"      author={{{' and '.join(authors)}}},",
        f"      year={{{year}}},",
        f"      eprint={{{paper_id}}},",
        "      archivePrefix={arXiv},",
    ]
    if primary_class:
        lines.append(f"      primaryClass={{{primary_class}}},")
    lines[-1] = lines[-1].replace(",", "")
    lines.append("}")
    return "\n".join(lines)


def _build_metadata_lines(metadata: dict[str, Any]) -> list[str]:
    paper_id = str(metadata.get("paper_id") or "").strip()
    title = str(metadata.get("title") or "").strip() or paper_id
    authors = [str(item).strip() for item in (metadata.get("authors") or []) if str(item).strip()]
    categories = [str(item).strip() for item in (metadata.get("categories") or []) if str(item).strip()]
    published_at = str(metadata.get("published_at") or "").strip()
    version = metadata.get("version")
    lines = [f"# {title}", "", f"- paper_id: {paper_id}"]
    if authors:
        lines.append(f"- authors: {', '.join(authors)}")
    if categories:
        lines.append(f"- categories: {', '.join(categories)}")
    if published_at:
        lines.append(f"- published_at: {published_at}")
    if isinstance(version, int):
        lines.append(f"- version: v{version}")
    lines.append(f"- abs_url: {str(metadata.get('abs_url') or f'https://arxiv.org/abs/{paper_id}')}")
    return lines


def _build_metadata_content(metadata: dict[str, Any]) -> str:
    lines = _build_metadata_lines(metadata)
    abstract = str(metadata.get("abstract") or "").strip()
    lines.extend(["", "## Abstract", "", abstract or "Abstract unavailable."])
    return "\n".join(lines).strip()


def _build_overview_content(metadata: dict[str, Any], overview_text: str | None) -> str:
    lines = _build_metadata_lines(metadata)
    cleaned_overview = _clean_inline_text(overview_text or "")
    abstract = str(metadata.get("abstract") or "").strip()
    if cleaned_overview:
        lines.extend(["", "## Summary", "", cleaned_overview])
        if abstract and _clean_inline_text(abstract).lower() != cleaned_overview.lower():
            lines.extend(["", "## Abstract", "", abstract])
    else:
        lines.extend(["", "## Abstract", "", abstract or "Abstract unavailable."])
    return "\n".join(lines).strip()


def _strip_duplicate_heading(content: str, title: str) -> str:
    if not content:
        return ""
    lines = content.splitlines()
    cleaned_title = _clean_inline_text(title)
    while lines:
        current = lines[0].strip()
        if not current:
            lines.pop(0)
            continue
        stripped = re.sub(r"^#+\s*", "", current)
        if cleaned_title and _clean_inline_text(stripped).lower() == cleaned_title.lower():
            lines.pop(0)
            continue
        break
    return "\n".join(lines).strip()


def _build_full_text_content(metadata: dict[str, Any], raw_content: str) -> str:
    lines = _build_metadata_lines(metadata)
    abstract = str(metadata.get("abstract") or "").strip()
    if abstract:
        lines.extend(["", "## Abstract", "", abstract])
    body = _strip_duplicate_heading(raw_content, str(metadata.get("title") or ""))
    if body:
        lines.extend(["", "## Full Text", "", body])
    return "\n".join(lines).strip()


def _format_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__
