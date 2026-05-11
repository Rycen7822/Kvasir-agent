---
name: paper-reliability-verifier
description: Verify scholarly-paper reliability for AI-scientist agents by checking citation counts, venue level, journal level, publication type, and retraction/update status.
version: 0.1.0
last_updated: 2026-04-30
---

# Paper Reliability Verifier Skill

## When to use

Use this skill before a literature-review agent cites a paper as evidence for a research claim, related-work comparison, benchmark table, or survey conclusion.

## Non-negotiable rules

1. Do not scrape Google Scholar. Treat Google Scholar citation counts as manual-only evidence.
2. Do not equate OpenAlex / Semantic Scholar / Crossref citation counts with Google Scholar counts.
3. Do not treat workshop, short, demo, poster, companion, or extended-abstract papers as main-track full papers. ACL Anthology Findings is a confirmed ACL-family publication track and may be `strong_evidence` when its parent venue rank is top-tier.
4. Do not reduce paper reliability to a single number. Produce an evidence card with warnings.
5. If the paper is retracted, mark it `do_not_use`.

## Inputs

Preferred input:

```json
{"doi": "10.xxxx/yyyy", "title": "optional", "year": 2024}
```

Title-only input is allowed but should normally result in `needs_human_review` unless metadata is unambiguous.

When the available evidence is a paper title plus an arXiv URL, do not treat the arXiv URL as a confirmed acceptance venue. Record the arXiv URL as `paper.source_ids.arxiv_url`, and use the paper title plus optional year to query OpenReview when a likely venue ID is known, then ACL Anthology and DBLP for possible accepted conference/journal records.

## Data-source policy

### Citation counts

Priority order:
1. **OpenAlex Works**: `cited_by_count`, `counts_by_year`, `is_retracted`.
2. **Semantic Scholar Graph API**: `citationCount`, `influentialCitationCount`, `referenceCount`.
3. **Crossref REST API**: `is-referenced-by-count`, bibliographic metadata, update/retraction signals.
4. **Licensed sources**, if available: Scopus, Web of Science, Dimensions.
5. **Manual-only**: Google Scholar.

Citation counts differ across databases. Report source-specific counts and `checked_at`.

### Confirmed accepted conference / journal ranking

This skill separates two questions:

1. **Acceptance detection**: whether the paper has really been accepted by a specific conference or journal.
2. **Ranking verification**: once the accepted venue/journal is known, what CCF/CORE/中科院分区/JCR authority signal that venue has.

The current implemented routes include explicit user confirmation, OpenReview, ACL Anthology, DBLP, and conservative Crossref Works metadata fallback. The stable `accepted_publication` interface leaves room for later publisher pages, OpenAlex source metadata, conference accepted-paper lists, or manual review without changing downstream ranking lookup fields.

Authoritative local ranking snapshots must be read from:

```text
/home/xu/project/ds_dev/paper_reliability_verifier_skill/paper_ranking
```

Expected files:

```text
conference_ranking.csv
journal_ranking.csv
```

During local development, if that directory is absent, the script may fall back to the skill-local copy:

```text
/home/xu/project/ds_dev/paper_reliability_verifier/paper_ranking
```

The production path above remains the canonical source. It can also be overridden with `PAPER_RANKING_DIR` for tests.

For a confirmed conference, use `conference_ranking.csv` and keep only these authority signals in the evidence card:

- accepted venue name and acronym;
- `CCF等级`;
- `CORE等级`;
- `CCF领域` when available;
- `数据来源` and `匹配依据`;
- `CORE名称别名` only as a caveat when the CORE title differs from the CCF title.

For a confirmed journal, use `journal_ranking.csv` and keep:

- journal name and abbreviation;
- `CCF等级` and `CCF领域` when available;
- `中科院大类`, `中科院大类分区`, `中科院 Top`, `WOS索引`;
- `中科院小类分区` and `特殊标注` for caveats;
- `数据来源`.

Do not infer ranking from publisher reputation, citations, or abstract claims when the local CSV has no match. Mark the rank as `unknown` and add a warning.

### Acceptance-detection compatibility interface

Until automatic acceptance detection is implemented, callers can pass confirmed publication information explicitly:

```bash
python scripts/verifier.py \
  --title "paper title" \
  --arxiv-url "https://arxiv.org/abs/xxxx.xxxxx" \
  --accepted-venue "AAAI Conference on Artificial Intelligence" \
  --accepted-type conference \
  --accepted-acronym AAAI
```

or for journals:

```bash
python scripts/verifier.py \
  --doi "10.xxxx/yyyy" \
  --accepted-venue "ACM Computing Surveys" \
  --accepted-type journal
```

The output includes an `accepted_publication` object with a stable interface version. Future automatic detection should fill the same object instead of changing downstream ranking lookup fields.

### Crossref Works accepted journal/proceedings fallback

Crossref is used both for DOI metadata/citation/update signals and as a conservative accepted-publication fallback after OpenReview, ACL Anthology, and DBLP do not confirm a venue. It follows the current Swagger/OpenAPI docs at:

```text
https://api.crossref.org/swagger-ui/index.html
https://api.crossref.org/swagger-docs
```

Implemented endpoint patterns:

```text
GET /works/{doi}
GET /works?query.title=...&filter=from-pub-date:YYYY-01-01,until-pub-date:YYYY-12-31&select=...
```

Rules:

1. Prefer DOI match from `/works/{doi}` when DOI is available.
2. For title-only fallback, require high title similarity and year match when year is known.
3. Treat `journal-article` with `container-title` as a confirmed journal publication.
4. Treat `proceedings-article` or records with a Crossref `event.name` as conference/proceedings evidence.
5. Treat `posted-content` and arXiv/bioRxiv/medRxiv/preprint containers as preprint, not accepted journal/conference evidence.
6. Preserve Crossref `update-to`, `relation`, `ISSN`/`ISBN`, publisher, URL, and `is-referenced-by-count` under `accepted_publication.crossref` for auditability.
7. Use `CROSSREF_MAILTO` as both query `mailto` and User-Agent mailto when available.

Status values include:

```text
crossref_confirmed
crossref_preprint_or_unclassified
crossref_not_found_or_ambiguous
```

Use `--no-crossref` to disable this fallback when testing stricter OpenReview/ACL/DBLP-only behavior.

### OpenReview accepted-venue and presentation-type detection

OpenReview is the specialized route for OpenReview-hosted venues such as ICLR, TMLR, COLM, UAI, and related workshops. Use it when a venue ID is known or strongly inferred; do not treat OpenReview as a global publication registry.

Embedded subskill:

```text
subskills/openreview-accepted-venue/SKILL.md
```

Primary documentation:

```text
https://docs.openreview.net/how-to-guides/data-retrieval-and-modification/how-to-get-all-notes-for-submissions-reviews-rebuttals-etc
```

Implemented route:

1. Load OpenReview credentials from `/home/xu/.hermes/secrets/openreview.env` if present, without printing them.
2. For API 2 venues, query accepted submissions with `get_all_notes(content={"venueid": venue_id}, details="replies")`.
3. For older API 1 venues, support `Blind_Submission` plus `details="directReplies,original"` and parse direct replies ending in `Decision`.
4. Match by normalized title similarity, default `>= 0.92`.
5. Parse acceptance separately from presentation type (`oral`, `spotlight`, `poster`, `accepted_unknown_presentation_type`, `rejected`).

The output fills the same `accepted_publication` object with status values such as:

```text
openreview_confirmed
openreview_not_accepted
openreview_not_found_or_ambiguous
```

Use `--openreview-venue-id ICLR.cc/2024/Conference` for explicit venue queries. If only `OPENREVIEW_VENUE_IDS` is set, the verifier can use that list as candidate venues.

### ACL Anthology accepted-venue detection

ACL Anthology is the first specialized automatic route for NLP / computational-linguistics publications when the paper may be in ACL, EMNLP, NAACL, EACL, AACL, COLING, CoNLL, TACL, CL, Findings, or related ACL Anthology workshops. It is used before DBLP when the user has not supplied a confirmed accepted venue.

Embedded subskill:

```text
subskills/acl-anthology-accepted-venue/SKILL.md
```

Python package documentation:

```text
https://acl-anthology.readthedocs.io/py-v1.1.0/
```

Implemented route:

1. Use `acl_anthology.Anthology.from_repo()` to locate/update the official ACL metadata checkout.
2. Search the local ACL XML metadata by DOI or conservative title/year match.
3. Extract Anthology ID, paper URL/PDF URL, volume title, venue ID/acronym/name, and DOI.
4. Fill the same `accepted_publication` object with statuses such as:

```text
acl_anthology_confirmed
acl_anthology_not_found_or_ambiguous
```

Rules:

1. If the user provides `--accepted-venue`, trust that explicit confirmed venue and skip automatic routes as the deciding signal.
2. Accept ACL Anthology hits only by exact DOI or high normalized title similarity; year must match when known.
3. Map ACL/EMNLP/NAACL/EACL/AACL/COLING/CoNLL style venues to `conference`; map TACL/CL to `journal`.
4. Preserve `volume_title` distinctions: ACL Anthology Findings should inherit the parent ACL-family venue for ranking, while workshops, short/demo papers, tutorials, shared tasks, and other non-main-track records must keep warnings.
5. If ACL Anthology results are absent, ambiguous, or low-similarity, do not fabricate a venue; continue to DBLP or unconfirmed open metadata fallback.

### DBLP accepted-venue detection

DBLP is the broad CS automatic route for the question “has this CS paper been indexed as a conference or journal publication, and under which venue?” It is used after ACL Anthology for NLP/CL candidates and before falling back to unconfirmed OpenAlex/Crossref/Semantic Scholar source names.

Embedded subskill:

```text
subskills/dblp-accepted-venue/SKILL.md
```

DBLP API documentation:

```text
https://dblp.uni-trier.de/faq/How+to+use+the+dblp+search+API.html
```

Implemented endpoint:

```text
https://dblp.org/search/publ/api?q=<query>&format=json&h=10&c=0
```

Rules:

1. If the user provides `--accepted-venue`, trust that explicit confirmed venue and skip DBLP as the deciding signal.
2. Otherwise query DBLP by title plus optional year/authors.
3. Accept a DBLP hit only when DOI matches or normalized title similarity is high enough; year must match when known.
4. Map `conf/...` and DBLP conference/workshop/proceedings types to `conference`.
5. Map `journals/...` and journal types to `journal`, except `journals/corr/...` / `CoRR`, which is only a preprint signal.
6. If DBLP results are ambiguous or low-similarity, return a warning and do not fabricate a venue.

The output still uses the same `accepted_publication` object. DBLP fills it with status values such as:

```text
dblp_confirmed
dblp_preprint_or_unclassified
dblp_not_found_or_ambiguous
```

This preserves compatibility with later routes such as Crossref event metadata, OpenAlex source metadata, publisher pages, or conference accepted-paper lists.

### Venue level

For CS/ML/AI:
1. Normalize venue names using DBLP and local alias tables.
2. Lookup CCF and CORE ranks from a local snapshot.
3. Confirm publication form: main-track full/regular paper, ACL Anthology Findings, versus workshop/short/demo/poster.
4. If track is unknown, add `track_unknown` and set `needs_human_review`.

### Journal level

Priority order:
1. Local CCF journal snapshot.
2. 中科院期刊分区数据源 if institutionally licensed.
3. SCImago/SJR as public fallback.
4. OpenAlex Sources `summary_stats` as open coarse fallback.
5. Manual review if title/ISSN matching is ambiguous.

Journal metrics are venue-level proxies. They are not proof that a specific paper’s claim is correct.

## Required output

Return a JSON object matching `schemas/paper_evidence_card.schema.json`.

Decision tiers:
- `do_not_use`: retracted, severe metadata mismatch, known fraud/paper-mill signal.
- `strong_evidence`: top venue or high-quality journal, not retracted, accepted publication independently confirmed; ACL Anthology Findings may qualify by inheriting its parent ACL-family venue rank.
- `supporting_evidence`: credible but not core evidence, or moderate citations.
- `weak_or_contextual_evidence`: preprint-only, workshop-only, short/demo, older low-citation paper.
- `needs_human_review`: DOI/title mismatch, missing venue track, conflicting ranks, suspicious citation discrepancy.

## Synthesis policy

When writing related work:
- Use `strong_evidence` papers for main claims.
- Use `supporting_evidence` for secondary support.
- Use `weak_or_contextual_evidence` only with caveats.
- Do not cite `do_not_use` papers except to discuss invalid or retracted work.
- Surface `needs_human_review` before final synthesis.
