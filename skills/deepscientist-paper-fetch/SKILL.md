---
name: deepscientist-paper-fetch
description: Use when a DeepScientist quest needs quest-local paper retrieval, arXiv/OpenReview PDF reading, or official resource verification without clipping into llm-wiki.
skill_role: support
version: 1.0.0
author: Codex Agent
license: MIT
metadata:
  hermes:
    tags: [deepscientist, research, arxiv, openreview, pdf, literature]
    related_skills: [scout, baseline, write]
---

> Codex adapter note: this stage skill is bundled for the DeepScientist Codex native plugin. Use `scripts/dsctl.py call <ds_tool_name> --json ... --format json` for DeepScientist state instead of unavailable Hermes/MCP tool calls. Do not use MCP transport or the external `ds` command. Runtime state lives under `<project>/DeepScientist/`.

# Paper Fetch

## Overview

This support skill is for **DeepScientist research work**, not note-taking archival.
Use it to retrieve, read, and verify papers for a quest, then persist the findings into DeepScientist memory, artifacts, baseline records, literature reports, or paper evidence ledgers.

Keep this skill separate from `clip`:

- `clip` archives sources into `llm-wiki` / Obsidian-style raw notes.
- `paper-fetch` gets paper evidence for the current DeepScientist quest.

Do not update `llm-wiki`, `raw/clip`, `_meta` maps, topic indexes, image archives, or clipping logs from this skill unless the user explicitly asks for clipping/archiving as a separate task.

## When to Use

Use `paper-fetch` when:

- a DeepScientist `scout`, `baseline`, `idea`, `write`, `finalize`, or `rebuttal` stage needs a specific paper read closely;
- the quest needs arXiv / OpenReview PDF text, metadata, or official first-party links;
- a baseline paper, method paper, benchmark paper, dataset paper, or citation must be grounded in primary sources;
- OpenReview anonymous/public PDF access is blocked, slow, or incomplete and authenticated retrieval may be needed;
- the agent needs to distinguish official project/code/model/dataset links from third-party search results.

Do **not** use this skill for:

- ordinary webpage clipping;
- WeChat / X / company blog archival;
- creating `YYMMDDNN_*.md` notes under `llm-wiki/raw/clip`;
- localizing article images into `raw/images`;
- updating `llm-wiki/index.md`, `_meta/raw-clip-map.md`, `_meta/topic-map.md`, or `log.md`;
- producing long standalone paper summaries that do not change the quest's next action.

## Output Contract for DeepScientist

For every paper retrieval that materially affects the quest, leave a durable quest-local record. Prefer one of these surfaces depending on the stage:

- `ds_memory_write` for compact paper facts, constraints, official-resource status, or citation notes.
- `ds_artifact_record` for a structured retrieval report, literature-scout report, or evidence item.
- Stage-specific tools such as `ds_confirm_baseline`, `ds_record_main_experiment`, `ds_submit_paper_outline`, or `ds_submit_paper_bundle` when the paper is tied to that artifact type.
- Quest-local files under artifacts/reports/literature/baselines/paper evidence directories when a longer report is needed, then register them with the relevant `ds_*` tool.

Minimum durable fields:

- paper title, authors if known, venue/date/version when available;
- source URL(s): original user URL, canonical abs/forum URL, PDF URL, HTML/source mirror if actually used;
- retrieval route and status: arXiv API, abs page, PDF extraction, arXiv HTML, OpenReview authenticated API, arXiv twin fallback, etc.;
- what was read: abstract only, metadata only, PDF body, HTML body, forum discussion, supplementary material;
- official-resource findings: project page, GitHub repo, model, dataset, benchmark, supplementary material, or explicitly “not exposed on checked first-party surfaces”;
- caveats and failure modes: 403, 404, rate limit, HTML unavailable, extraction noisy, authenticated route unavailable;
- next-action relevance for the quest.

## General Retrieval Discipline

1. Normalize the input URL before fetching.
2. Prefer primary sources over search snippets.
3. Read enough of the actual paper body to support the decision being made.
4. Verify first-party code/data/project links directly before treating them as official.
5. Record scoped absence carefully: “no official public code found on abs/PDF/project/forum surfaces checked” is better than “no code exists”.
6. Keep temporary PDF/text/metadata files out of the final quest unless they are intentionally registered as artifacts.
7. Clean temporary directories after extracting the evidence you need.
8. Before deleting a temp directory, ensure the process working directory is outside it; deleting the current cwd can break later tool calls.

## arXiv Route

### Normalize

- `https://arxiv.org/abs/<id>` -> preserve abs URL and derive `https://arxiv.org/pdf/<id>`.
- `https://arxiv.org/pdf/<id>` -> derive and preserve matching abs URL.
- `https://arxiv.org/html/<id>` -> derive abs and PDF URLs; preserve HTML only after confirming it is real paper HTML.
- `https://huggingface.co/papers/<arxiv_id>` -> treat as a discovery mirror and normalize to arXiv abs/PDF.

### Preferred order

1. Try DeepScientist/Codex paper reading primitives if available, e.g. `artifact.arxiv(paper_id=..., full_text=False)` for actual arXiv reading.
2. Use web search for discovery; do not use paper-reading tools just to locate candidates.
3. Fetch metadata from the arXiv API when stable.
4. If the arXiv API returns `503`, malformed XML, empty content, or transient failures, parse the abs page metadata immediately.
5. Fetch/extract the PDF body for method/results/details that affect the quest.
6. Use arXiv HTML as a grounded fallback or complement for section structure, tables, captions, and first-party links when available.
7. If Python HTTPS fetches are flaky, retry the extensionless arXiv PDF route `https://arxiv.org/pdf/<id>` when `https://arxiv.org/pdf/<id>.pdf` fails, then retry with `curl -L --http1.1` before declaring the paper unreachable.

### What to preserve

- canonical unversioned abs/PDF URL;
- actual versioned URL/date if discovered;
- HTML URL only if it returned real useful paper HTML;
- DOI when exposed by metadata or abs-page DOI row;
- project/code/dataset/model/benchmark links only when confirmed from paper-owned surfaces.

### Extraction notes

- Prefer `pypdf` or PyMuPDF/`fitz` when available.
- If `execute_code` and terminal Python have different packages, retry with terminal `python3` or the known project environment before assuming extraction libraries are missing.
- First inspect the front matter / first 150-200 extracted lines; they often expose venue, official code, project page, and headline claims.
- PDF text can omit or truncate hyperlinks. If a front-page anchor says “Code available here” but no URL appears in text, inspect PDF annotations/hyperlinks with PyMuPDF and check arXiv HTML/front-matter links.

### Official-resource verification

Do not treat generic UI widgets or arbitrary PDF bibliography URLs as official resources.

Check in this order:

1. abs page metadata and visible links;
2. arXiv HTML front matter / title-region links;
3. PDF front matter/body and PDF hyperlink annotations;
4. project page, if exposed;
5. official repo README/root contents/API;
6. official Hugging Face model/dataset/collection API when relevant;
7. exact-title/acronym search only as a sanity check, not as proof.

Record distinctions:

- first-party official resource;
- third-party reproducibility dependency;
- official repo exists but public substance is incomplete;
- project page exists but code says “coming soon”;
- no first-party official link found on checked paper-owned surfaces.

## OpenReview Route

### Normalize

- `https://openreview.net/forum?id=<note_id>` -> preserve forum URL and derive `https://openreview.net/pdf?id=<note_id>`.
- `https://openreview.net/pdf?id=<note_id>` -> derive and preserve forum URL.
- For hashed/non-canonical PDF URLs, try to recover the canonical note/forum id from authenticated metadata, venue listings, or exact title matching before giving up.

### Authentication and security

Use credentials only from the local secret file:

```text
~/.hermes/secrets/openreview.env
```

Expected keys:

- `OPENREVIEW_USERNAME`
- `OPENREVIEW_PASSWORD`

Rules:

- Do **not** print credentials.
- Do **not** store credentials in quest memory, artifacts, logs, notes, or final replies.
- Do **not** blindly `source` the env file in bash; passwords may contain shell-significant characters.
- Parse the env file as plain text in Python, splitting on the first `=`.
- Prefer `/home/xu/miniconda3/envs/test/bin/python3` for authenticated OpenReview retrieval in this workspace.
- Prefer `openreview.api.OpenReviewClient` with `baseurl='https://api2.openreview.net'`.

### Preferred order

1. Parse note id and canonical forum/PDF URLs.
2. Try authenticated metadata with `OpenReviewClient` or `client.session.get('https://api2.openreview.net/notes?id=<note_id>', headers=client.headers)`.
3. Fetch the PDF through the authenticated API route.
4. If `client.get_pdf(note_id)` is slow/hangs, reuse the authenticated headers with `curl -L --http1.1 -H 'Authorization: ...' -H 'Accept: application/pdf' https://api2.openreview.net/pdf?id=<note_id>`.
5. Extract the PDF body with PyMuPDF/`fitz` or `pypdf`.
6. Inspect forum metadata for title, authors, abstract, keywords, TLDR/TL;DR, venue/status, supplementary material, and canonical hashed PDF path.
7. If OpenReview PDF transfer is too slow but the same paper has a public arXiv twin, use the arXiv twin for detailed reading while preserving the original OpenReview forum/PDF links and noting the fallback route.

### Rate limits and browser fallback

- Repeated OpenReview login can trigger `429 Too Many Requests`. Stop retrying immediately; wait for the reset window and retry once.
- Browser navigation to OpenReview can time out even when authenticated API retrieval works. Do not interpret browser timeout as paper absence.
- If all authenticated routes fail, public forum metadata/discussion may still be useful; label the result as forum-grounded rather than full-PDF-grounded.
- Browser navigation to `/pdf?id=...` may only start a download; it does not mean the PDF body has been read.

### Supplementary material and code

- Normalize OpenReview supplementary material to a stable URL when available, preferably `https://openreview.net/attachment?id=<note_id>&name=supplementary_material`.
- If code exists only inside supplementary material, record that distinction; do not mislabel it as a public repo.
- If the paper/front matter exposes a project page, inspect the project page before finalizing resource status.
- If a GitHub repo is official, verify root contents and README/API before describing reproducibility readiness.
- If metadata authors are empty and the PDF says anonymous/double-blind, do not hallucinate names.

### Cleanup

Use a per-paper temp directory such as:

```text
/tmp/openreview_<note_id>/
```

It may contain `paper.pdf`, `paper.txt`, `metadata.json`, `urls.txt`, and extraction status files. Delete it after you have persisted the quest evidence. Confirm it is gone. Do not delete it while the active shell/tool cwd is inside it.

## ACM Digital Library Route

Treat ACM DL as a primary metadata/source surface, but do not try to bypass access controls.

### Normalize

- `https://dl.acm.org/doi/<doi>` -> preserve as the ACM landing page and derive:
  - `https://doi.org/<doi>`
  - `https://dl.acm.org/doi/pdf/<doi>`
  - `https://dl.acm.org/doi/epdf/<doi>` only as an access check, not as a guaranteed body source.
- DOI-only input such as `10.1145/...` -> derive DOI resolver and ACM DOI paths when the publisher is ACM.

### Preferred order

1. Try the ACM landing page and `/doi/pdf/...` route with normal HTTP/browser access.
2. If ACM DL returns Cloudflare/challenge, `403`, institutional-login, or paywall responses, record that exact status and stop retrying aggressively.
3. Fetch bibliographic metadata from Crossref and/or OpenAlex by DOI.
4. Check whether Crossref/OpenAlex marks the work as closed/open and whether any PDF URL is exposed.
5. Search for an author-allowed/open twin by exact title, especially arXiv, institutional repository, or author project page.
6. If an open twin is found, download/read that version while preserving the ACM DOI as the canonical published source and caveating version differences.
7. If only closed ACM access exists, report `metadata_only` rather than using unauthorized mirrors.

### What to record

- ACM DOI and landing page;
- ACM PDF route status, e.g. `403 Cloudflare challenge`, `paywalled`, `institutional login required`, or `downloaded`;
- Crossref/OpenAlex title, venue, publication date, and OA status;
- open twin URL and version if used, e.g. arXiv id/version;
- whether the retrieved PDF is publisher VOR or an author/preprint version.

## Unpaywall Fallback Route

Use Unpaywall when primary/source-specific routes cannot provide a legal downloadable PDF:

- publisher/platform database cannot be downloaded directly because of paywall, institutional login, Cloudflare/challenge, `403`, `404`, or rate limits;
- arXiv has no matching paper or arXiv download fails;
- GitHub does not expose a paper PDF;
- the official project page does not host a paper PDF;
- Crossref/OpenAlex metadata exists but no direct primary PDF is usable.

Unpaywall is a fallback for legal open-access copies. Do not use it to fetch unauthorized mirrors. Preserve the publisher DOI/source as canonical when the Unpaywall location is a repository or submitted/accepted manuscript.

### Email and secret handling

Unpaywall requires a contact email. Never hard-code a user's email in this skill, source files, tests, reports, git commits, or examples.

Read the email only from the local secret file:

```text
~/.hermes/secrets/research.env
```

Expected key:

```text
UNPAYWALL_EMAIL=<user email>
```

If `UNPAYWALL_EMAIL` is missing, stop and ask the user to provide an email, then tell them to add it to `~/.hermes/secrets/research.env` under the `UNPAYWALL_EMAIL` key. Do not guess, invent, or reuse unrelated credentials.

Safe Python pattern:

```python
from pathlib import Path

def read_unpaywall_email() -> str:
    path = Path.home() / ".hermes" / "secrets" / "research.env"
    if not path.exists():
        raise RuntimeError("Missing ~/.hermes/secrets/research.env; ask user to add UNPAYWALL_EMAIL=<email>.")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("UNPAYWALL_EMAIL="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise RuntimeError("Missing UNPAYWALL_EMAIL in ~/.hermes/secrets/research.env; ask user to add it.")
```

Do not print the email in final replies unless the user explicitly asks to inspect their own local secret configuration. When reporting, say only that the email was read from the local secret file.

### Query recipe

```bash
# Export UNPAYWALL_EMAIL from ~/.hermes/secrets/research.env in a wrapper script or Python subprocess env.
# Do not commit or echo the concrete value.
curl -s "https://api.unpaywall.org/v2/<doi>?email=$UNPAYWALL_EMAIL" \
  | jq '{
      doi,
      title,
      is_oa,
      oa_status,
      pdf: .best_oa_location.url_for_pdf,
      landing: .best_oa_location.url,
      host_type: .best_oa_location.host_type,
      version: .best_oa_location.version
    }'
```

### Preferred order

1. Query Unpaywall by DOI with the email read from `~/.hermes/secrets/research.env`.
2. Check `is_oa`, `oa_status`, `best_oa_location.url_for_pdf`, `best_oa_location.url`, `host_type`, and `version`.
3. Prefer `url_for_pdf` when present; otherwise inspect `url`/landing page only if it is a legal open repository or publisher page.
4. Download with `curl -L --http1.1 --fail --retry 3`.
5. Verify PDF header (`%PDF`), file size, hash, and page count/text extraction with PyMuPDF or `pypdf`.
6. Record whether the file is `publishedVersion`, `acceptedVersion`, `submittedVersion`, or another repository version.
7. Caveat clearly when the downloaded file is not the publisher final PDF.

### What to record

- DOI and original source/platform route that failed or was unavailable;
- Unpaywall `is_oa`, `oa_status`, `host_type`, `version`;
- PDF URL and landing URL actually used;
- file path, byte size, checksum, page count, and extraction status when downloaded;
- version caveat, e.g. `repository submittedVersion`, `accepted manuscript`, or `publisher VOR`.

## Direct PDF / Other Hosts

Treat direct PDFs as paper-reading requests, not webpage clipping.

- GitHub `blob/.../*.pdf` -> preserve blob URL, derive `raw.githubusercontent.com/...`, download/extract PDF, inspect repo README/API for official implementation status.
- Hugging Face repo-hosted PDF -> preserve original `blob` URL, derive `/resolve/...` download URL, inspect model/dataset/card/API for metadata, license, checkpoint/data status when relevant.
- CVF/OpenAccess PDF -> derive and fetch matching OpenAccess HTML page when possible for citation metadata, abstract, pages, related materials, and code/arXiv links.
- Other direct PDFs -> fetch/extract; preserve original URL and any landing page if known.

## What Not to Copy from `clip`

Do not bring these archive-specific behaviors into DeepScientist paper fetching:

- `YYMMDDNN_<title>.md` raw-note naming;
- duplicate checks across `llm-wiki/raw/clip`;
- image localization under `raw/images`;
- obclip browser workflows;
- WeChat/X hostile-page clipping;
- promo/ad/footer cleanup for article preservation;
- `_meta/raw-clip-map.md`, `_meta/topic-map.md`, `index.md`, or `log.md` updates;
- treating a paper retrieval as a wiki ingest.

If the user explicitly asks to archive a paper into `llm-wiki`, stop using this skill as the primary procedure and load `clip` instead.

## Minimal Quest-local Report Template

Use or adapt this shape when recording a retrieval report:

```markdown
# Paper Retrieval Report

- quest_id:
- paper_id / note_id:
- title:
- authors:
- venue / version / date:
- original_url:
- canonical_abs_or_forum_url:
- pdf_url:
- html_or_mirror_url_used:
- retrieval_route:
- body_read_status: metadata_only | abstract_only | pdf_body | html_body | forum_discussion | arxiv_twin
- official_resources_checked:
  - project_page:
  - code_repo:
  - dataset:
  - model/checkpoint:
  - supplementary:
- scoped_absence_or_caveats:
- quest_relevance:
- next_action:
```

## Verification Checklist

Before finishing a paper-fetch task:

- [ ] The retrieval result is recorded in quest memory/artifacts or a stage-specific DeepScientist record.
- [ ] Original and canonical source URLs are preserved.
- [ ] The agent records exactly which body surface was read.
- [ ] Official resources are verified directly or caveated.
- [ ] No `llm-wiki` clipping/index/raw-note work was performed unless explicitly requested.
- [ ] OpenReview credentials were not printed or persisted.
- [ ] Temporary PDF/text/metadata directories are cleaned up when no longer needed.
- [ ] The result clearly says how the evidence changes the quest's next action.
