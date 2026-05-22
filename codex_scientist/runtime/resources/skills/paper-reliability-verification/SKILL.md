---
name: paper-reliability-verification
description: Verify paper reliability through the bundled CodexScientist verifier workflow before using papers as evidence.
version: 1.1.2
author: CodexScientist Codex adapter
license: MIT
metadata:
  hermes:
    tags: [research, papers, reliability, citations, openreview, acl-anthology, dblp, crossref, venue-ranking, cas-partition, ccf, core]
    category: research
    related_skills: [research-paper-writing, csv-taxonomy-consolidation, arxiv]
skill_role: companion
---

> Codex adapter note: this is a Codex-packaged CodexScientist support skill. Prefer public MCP `cs_*` tools visible in `tools/list`/`cs_tool_schema` for durable root-bound research state, memory, artifacts, and recovery anchors; use admin CLI fallbacks only when explicitly following docs/ADMIN_CLI.md. Load it only when it is the relevant companion to the active stage.
> Use `cs_paper_reliability_verify` as the primary CodexScientist tool wrapper; it stores reliability cards under project-local `reference/reliability_cards/` and keeps `accepted_publication` evidence auditable.

# Paper Reliability Verification

## Overview

Use this skill when a literature review, research plan, survey, or paper-writing task needs to decide whether a candidate paper is strong evidence, supporting evidence, weak/contextual evidence, or needs human review.

The core pattern is: **do not treat a paper as reliable merely because it was found or downloaded**. Verify citation signals, publication status, accepted venue/journal, and venue authority separately, then combine them conservatively.

Recent local verifier extensions added OpenReview as a first-class accepted-venue route for known OpenReview-hosted venues (for example ICLR), while preserving the same `accepted_publication` output contract as ACL Anthology and DBLP.

For this user's current workspace, the working draft verifier lives at:

```text
resources/skills/paper-reliability-verifier
```

The local ranking snapshots used for accepted conference/journal authority checks live at:

```text
resources/skills/paper-reliability-verifier/paper_ranking
```

Expected ranking files:

```text
conference_ranking.csv
journal_ranking.csv
```

## When to Use

Use this skill when:

- evaluating papers found during literature review or CodexScientist research;
- checking whether a paper's accepted conference/journal is authoritative;
- comparing venue rank signals such as CCF, CORE, 中科院期刊分区, WOS index, or 中科院 Top;
- separating preprint-only evidence from conference/journal accepted publications;
- generating an evidence card before citing a paper as key support;
- extending the local `paper_reliability_verifier` skill/tool with another source of acceptance evidence.

Do not use this skill for:

- merely downloading PDFs; use the CodexScientist `paper-fetch` workflow for retrieval;
- llm-wiki clipping/archive tasks;
- claiming Google Scholar citation counts from automation. Google Scholar is manual-only.

## First Principles

Separate these questions:

1. **Identity:** Is this the same paper? Match DOI, title, authors, and year.
2. **Publication status:** Is it retracted, corrected, preprint-only, workshop-only, short/demo/poster, or main-track/full?
3. **Acceptance venue:** Has it been indexed or confirmed as accepted by a specific conference or journal?
4. **Venue authority:** What do local CCF/CORE/JCR ranking snapshots say about that confirmed venue?
5. **Impact proxy:** What do OpenAlex, Semantic Scholar, and Crossref citation counts say? Keep counts source-specific.
6. **Decision tier:** Synthesize into a cautious tier with warnings, never a single blind score.

## Local Ranking Lookup

For confirmed conferences, look up:

```text
resources/skills/paper-reliability-verifier/paper_ranking/conference_ranking.csv
```

Key fields:

- `会议名称`
- `简称`
- `CCF等级`
- `CORE等级`
- `CCF领域`
- `数据来源`
- `匹配依据`
- `CORE名称别名`

For confirmed journals, look up:

```text
resources/skills/paper-reliability-verifier/paper_ranking/journal_ranking.csv
```

Key fields:

- `期刊名称`
- `简称`
- `CCF等级`
- `CCF领域`
- `中科院大类`
- `中科院大类分区`
- `中科院 Top`
- `WOS索引`
- `中科院小类分区`
- `特殊标注`
- `数据来源`

Keep CCF, CORE, 中科院分区, and Clarivate JCR fields separate. Do not collapse them into one universal rank. For this user's verifier, `journal_ranking.csv` contains both 中科院分区 (`中科院大类分区`/`中科院小类分区`, output `journal.cas_quartile`) and merged JCR 2024 fields (`JCR分区2024`/`JCR影响因子2024`, output `journal.jcr_quartile` and `journal.impact_factor`). Older local snapshots may still contain legacy `JCR*` column names that actually meant 中科院; treat those only as backward-compatible aliases.

## OpenReview Accepted-Venue Detection

OpenReview is the first specialized automatic route when the target paper belongs to a **known OpenReview-hosted venue** such as ICLR, TMLR, COLM, or another venue with a supplied venue ID. Use it before ACL Anthology and DBLP only when a venue ID is known from `--openreview-venue-id` or a trusted environment/config mapping; do not perform ambiguous global OpenReview guessing.

Detailed session notes, implementation contract, and verified commands are in:

```text
references/openreview-accepted-venue.md
```

For tasks that ask to discover/download all public papers from an OpenReview-hosted venue matching a topic (rather than verify one paper's authority), use the companion operational reference:

```text
references/openreview-public-proceedings-download.md
```

That reference covers probing whether ICLR/ICML-style venue submissions are public, filtering accepted notes by title/abstract/keywords, downloading PDFs from stored `/pdf/<hash>.pdf` values with `pdf?id=` fallback, writing a manifest, and verifying every manifest PDF with `ls -lh`, `%PDF-` header, size, and SHA256.

Implementation pattern:

1. Preserve explicit user confirmation priority: `--accepted-venue` stays stronger than all automated routes.
2. If a trusted OpenReview venue ID is available, query OpenReview before ACL Anthology and DBLP.
3. For API 2 venues, prefer `client.get_all_notes(content={"venueid": venue_id}, details="replies")` and match title/year conservatively.
4. For older API 1 venues, search blind submissions and inspect direct `Decision` replies.
5. Separate acceptance from presentation: `accepted=true` confirms venue acceptance; `presentation_type` stores `oral`, `spotlight`, `poster`, or `accepted_unknown_presentation_type`.
6. Return `openreview_confirmed` only for high-confidence title/venue matches; return a warning or ambiguous status for no-close-match, not-found, rejected, or low-confidence cases.

In the local verifier, this logic is documented in:

```text
resources/skills/paper-reliability-verifier/subskills/openreview-accepted-venue/SKILL.md
```

## ACL Anthology Accepted-Venue Detection

ACL Anthology is the specialized automatic route for NLP / computational-linguistics accepted-venue detection when the paper may be in ACL, EMNLP, NAACL, EACL, AACL, COLING, CoNLL, TACL, CL, Findings, or ACL Anthology workshops. Use it after OpenReview when a known OpenReview venue ID has not confirmed the paper, and before DBLP when the user has not supplied a confirmed accepted venue.

Detailed session notes and verified commands are in:

```text
references/acl-anthology-accepted-venue.md
```

Implementation pattern:

1. Use `acl_anthology.Anthology.from_repo(verbose=False)` to locate/update the official ACL metadata checkout and obtain `anthology.datadir`.
2. For broad title/DOI search, scan `data/xml/*.xml` and venue YAML under `data/yaml/venues/*.yaml` instead of forcing global package indices.
3. Prefer exact DOI match; otherwise require high normalized title similarity, around `0.90`, plus year match when year is known.
4. Return `accepted_publication.status = acl_anthology_confirmed` only for high-confidence hits.
5. Map ACL/EMNLP/NAACL/EACL/AACL/COLING/CoNLL-style venues to `conference`; map TACL/CL to `journal`.
6. Preserve volume-title distinctions: ACL Anthology Findings is a confirmed ACL-family publication track and may be strong evidence by inheriting the parent ACL/EMNLP/NAACL/EACL/AACL/COLING/CoNLL venue rank; workshops, short/demo/tutorial/shared-task/poster/extended-abstract records remain non-main-track caveats.

Pitfall: the installed `acl-anthology` package can emit `SchemaMismatchWarning` when its bundled schema lags behind the latest downloaded metadata. Avoid building global venue/event/person indices unless needed; XML scanning from the package-managed data dir is more robust for verifier lookups.

In the local verifier, this logic is documented in:

```text
resources/skills/paper-reliability-verifier/subskills/acl-anthology-accepted-venue/SKILL.md
```

## Crossref Works Accepted-Publication Fallback

Crossref is used both for DOI metadata/citation/update signals and as a conservative accepted-publication fallback after OpenReview, ACL Anthology, and DBLP do not confirm a venue.

Detailed session notes, API quirks, implementation contract, and regression-test checklist are in:

```text
references/crossref-accepted-publication.md
```

Docs:

```text
https://api.crossref.org/swagger-ui/index.html
https://api.crossref.org/swagger-docs
```

Endpoint patterns:

```text
GET https://api.crossref.org/v1/works/{doi}
GET https://api.crossref.org/v1/works?query.title=...&filter=from-pub-date:YYYY-01-01,until-pub-date:YYYY-12-31&select=...
```

Rules:

1. Prefer DOI match from `/works/{doi}`.
2. For title-only fallback, require high title similarity and year match when year is known.
3. Treat `journal-article` with `container-title` as confirmed journal publication.
4. Treat `proceedings-article` or records with `event.name` as conference/proceedings evidence.
5. Treat `posted-content` and arXiv/bioRxiv/medRxiv/preprint containers as preprint-only.
6. Preserve `update-to`, `relation`, `ISSN`/`ISBN`, publisher, URL, and `is-referenced-by-count` under `accepted_publication.crossref`.
7. Use `CROSSREF_MAILTO` for query `mailto` and User-Agent mailto when available.

Status values:

```text
crossref_confirmed
crossref_preprint_or_unclassified
crossref_not_found_or_ambiguous
```

Use `--no-crossref` to disable this fallback.

## DBLP Accepted-Venue Detection

DBLP is the broad CS automatic route for accepted-venue detection after ACL Anthology does not confirm an NLP/CL paper.

DBLP docs:

```text
https://dblp.uni-trier.de/faq/How+to+use+the+dblp+search+API.html
```

Endpoint:

```text
https://dblp.org/search/publ/api
```

Canonical query:

```bash
curl -s 'https://dblp.org/search/publ/api?q=<title+authors+year>&format=json&h=10&c=0'
```

Use conservative hit selection:

1. Prefer exact DOI match when DBLP returns DOI.
2. Otherwise require high normalized title similarity, default around `0.88` or higher.
3. If year is known, require year match for title-based acceptance.
4. If low-similarity or ambiguous, return `dblp_not_found_or_ambiguous` and do not fabricate a venue.

Map DBLP records:

- `key` starts with `conf/` or type contains `Conference`, `Workshop`, or `Proceedings` -> conference-like venue.
- `key` starts with `journals/` or type contains `Journal` -> journal-like venue.
- `journals/corr/...` or venue `CoRR` -> preprint only; do **not** treat as conference/journal acceptance.

In the local verifier, this logic is documented in:

```text
resources/skills/paper-reliability-verifier/subskills/dblp-accepted-venue/SKILL.md
```

## Local Verifier Usage

Default OpenReview/ACL-Anthology/DBLP-enabled verification:

```bash
cd resources/skills/paper-reliability-verifier
python3 scripts/verifier.py \
  --title 'Graph Neural Networks for Learning Equivariant Representations of Neural Networks' \
  --year 2024 \
  --openreview-venue-id ICLR.cc/2024/Conference
```

Expected behavior for the OpenReview example:

- OpenReview is queried with the supplied venue ID before ACL Anthology and DBLP.
- A confirmed accepted ICLR paper fills `accepted_publication.status = openreview_confirmed`.
- ICLR presentation labels such as oral/spotlight/poster are captured in `accepted_publication.openreview.presentation_type`, not collapsed into the main venue type.
- local conference ranking resolves ICLR to its local CCF/CORE fields when available.

Default ACL/DBLP fallback verification:

```bash
cd resources/skills/paper-reliability-verifier
python3 scripts/verifier.py \
  --title 'Deep Residual Learning for Image Recognition' \
  --year 2016
```

Expected behavior for the example:

- For ACL/EMNLP/NAACL-style NLP papers, ACL Anthology is tried first and can fill `accepted_publication.status = acl_anthology_confirmed` with Anthology ID, URL/PDF URL, venue acronym/name, and volume title.
- If ACL Anthology does not confirm, DBLP searches broader CS records.
- DBLP finds `conf/cvpr/HeZRS16`.
- `accepted_publication.status` is `dblp_confirmed`.
- `venue_name` is `CVPR`.
- local conference ranking resolves CVPR to CCF A / CORE A*.

Disable OpenReview when testing fallback behavior:

```bash
python3 scripts/verifier.py --title 'paper title' --no-openreview
```

Disable DBLP when testing fallback behavior:

```bash
python3 scripts/verifier.py --title 'paper title' --no-dblp
```

Explicitly provide confirmed venue when an upstream/manual route already verified acceptance:

```bash
python3 scripts/verifier.py \
  --title 'paper title' \
  --accepted-venue 'AAAI Conference on Artificial Intelligence' \
  --accepted-type conference \
  --accepted-acronym AAAI
```

For confirmed journal:

```bash
python3 scripts/verifier.py \
  --doi '10.xxxx/yyyy' \
  --accepted-venue 'ACM Computing Surveys' \
  --accepted-type journal
```

## Output Contract

The verifier should preserve an `accepted_publication` object so future routes can plug in without changing rank lookup:

```json
{
  "status": "user_provided_confirmed | dblp_confirmed | dblp_preprint_or_unclassified | dblp_not_found_or_ambiguous | metadata_inferred_unconfirmed",
  "venue_name": "CVPR",
  "venue_type": "conference | journal | preprint | auto",
  "acronym": "CVPR",
  "evidence_source": "dblp publication search: title_year_match",
  "interface_version": "accepted-publication-v1"
}
```

Downstream ranking fields then appear under `venue` or `journal`, not inside citation fields.

## Verification Checklist

Before trusting a reliability result:

- [ ] The paper identity match is clear: DOI match or high title/year match.
- [ ] DBLP `CoRR` records were treated as preprints, not accepted venues.
- [ ] Accepted conference/journal rank was read from the local `paper_ranking` CSVs.
- [ ] CCF, CORE, and 中科院分区 ranks remain separate fields, with journal output using `cas_quartile` rather than `jcr_quartile`.
- [ ] Citation counts are source-specific and checked at a date.
- [ ] Retraction/update status was checked when DOI metadata is available.
- [ ] Workshop/short/demo/poster caveats are not suppressed; ACL Anthology Findings is handled separately as a confirmed ACL-family track that may be strong evidence after parent-venue rank lookup.
- [ ] Ambiguous venue detection results produce warnings or `needs_human_review`.
- [ ] Downstream filters use an explicit accepted-status allowlist, not substring matching. In particular, `metadata_inferred_unconfirmed` contains the text `confirmed` but is **not** a confirmed accepted publication.

## Common Pitfalls

1. **Using DBLP absence as proof of no acceptance.** DBLP is strong for CS but incomplete. Absence means unknown, not rejected.
2. **Treating CoRR as journal acceptance.** DBLP stores arXiv/CoRR under `journals/corr`; this is preprint evidence only.
3. **Ranking a guessed venue.** Only rank a confirmed or high-confidence accepted venue.
4. **Mixing venue authority with paper correctness.** CCF A / 中科院1区 supports authority but does not prove claims are true.
5. **Overusing fuzzy matches.** Keep fuzzy/low-confidence matches as human-review candidates unless similarity is high and year/DOI supports the match.
6. **Substring-testing verifier statuses.** Never use logic like `'confirmed' in status`: it misclassifies `metadata_inferred_unconfirmed` as confirmed. Use an explicit accepted-status whitelist such as `user_provided_confirmed`, `openreview_confirmed`, `acl_anthology_confirmed`, `dblp_confirmed`, and `crossref_confirmed`; treat `*_unconfirmed`, `*_not_found_or_ambiguous`, and `*_preprint_or_unclassified` as non-confirmed unless another trusted route/user instruction retains the paper.
7. **ArXiv/title-only citation gaps.** If a verifier card for a known arXiv paper has empty OpenAlex/Semantic Scholar/Crossref citation counts, do not immediately downgrade the paper. Supplement with arXiv DOI `10.48550/arXiv.<id>`, Semantic Scholar `ArXiv:<id>`, OpenAlex DOI/title search, DBLP CoRR metadata, or explicit accepted-venue input when externally verified. This is especially important for classic high-impact papers such as Universal Transformers, ACT, DEQ, and LoRA.
8. **ArXiv-only preprint status ambiguity.** When an input has an arXiv URL but no confirmed accepted venue/journal, treat it as preprint-unconfirmed even if a local card reports `is_preprint_only=false`; add a caveat until an accepted venue route confirms publication.
9. **ACL Anthology schema warnings during batches.** `SchemaMismatchWarning: Data directory contains a different schema.rnc as this library` can appear repeatedly in batch verification. It is noisy but not necessarily fatal; do not stop solely for this warning unless lookups fail. Prefer warning suppression/log capture in scripts and update ACL Anthology metadata/library in maintenance passes.
10. **Misclassifying ACL Anthology Findings as weak/non-main-track by default.** For this user's verifier policy, ACL Anthology Findings is a confirmed ACL-family publication track. If the hit is independently confirmed by ACL Anthology and the parent ACL-family venue rank is top-tier, it may be `strong_evidence`. Keep workshop, short, demo, tutorial, shared-task, poster, companion, and extended-abstract caveats separate; do not let the word `Findings` alone trigger non-main-track demotion.
