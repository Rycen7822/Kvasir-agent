---
name: dblp-accepted-venue
description: Use when paper-reliability-verifier needs to infer whether a CS paper is indexed by DBLP as a conference or journal publication before local CCF/CORE/中科院分区/JCR rank lookup.
version: 0.1.0
author: Codex Agent
license: MIT
metadata:
  hermes:
    tags: [dblp, publications, venue, reliability, paper-ranking]
    related_skills: [paper-reliability-verifier]
---

# DBLP Accepted Venue Detection

## Scope

This is an embedded support skill for `paper-reliability-verifier`. Its job is narrow:

1. Query DBLP publication search for a candidate paper.
2. Decide whether DBLP has a high-confidence publication record.
3. Extract the DBLP venue string and publication type.
4. Pass that venue to the parent verifier's local ranking lookup.

It does **not** replace local CCF/CORE/中科院分区/JCR ranking CSVs. DBLP answers “what venue DBLP indexed this paper under”; `paper_ranking/*.csv` answers “how authoritative is that confirmed venue”.

## DBLP API Route

Use the DBLP publication search API documented at:

```text
https://dblp.uni-trier.de/faq/How+to+use+the+dblp+search+API.html
```

Endpoint:

```text
https://dblp.org/search/publ/api
```

Important parameters:

```text
q       query string
format  json | xml | jsonp; use json
h       max hits, capped by DBLP; use 10-20 for verifier lookup
f       first hit offset for pagination
c       completion terms; set c=0 for paper verification
```

Canonical query shape:

```bash
curl -s 'https://dblp.org/search/publ/api?q=<title+authors+year>&format=json&h=10&c=0'
```

## Matching Rules

Prefer explicit user-provided accepted venue over DBLP. Use DBLP when the user has not provided venue/journal acceptance.

Accept a DBLP hit only when one of these is true:

1. DOI matches exactly.
2. Normalized title similarity is high enough, default `>= 0.88`, and year matches when year is known.
3. Normalized title similarity is high enough and it is the best hit when year is unknown.

If the top hits are low-similarity or ambiguous, do not guess. Return `dblp_not_found_or_ambiguous` and keep the top few hits in diagnostic evidence.

## Venue Type Mapping

Use DBLP `info.type` and `info.key`:

- `key` starts with `conf/` or type contains `Conference`, `Workshop`, or `Proceedings` -> `conference`.
- `key` starts with `journals/` or type contains `Journal` -> `journal`.
- `journals/corr/...` or venue `CoRR` -> `preprint`, not a confirmed journal/conference acceptance.
- Otherwise -> `auto` / unclassified.

## Output Contract to Parent Verifier

Return an `accepted_publication`-compatible object:

```json
{
  "status": "dblp_confirmed | dblp_preprint_or_unclassified | dblp_not_found_or_ambiguous",
  "venue_name": "CVPR",
  "venue_type": "conference",
  "acronym": "CVPR",
  "evidence_source": "dblp publication search: title_year_match",
  "interface_version": "accepted-publication-v1",
  "dblp": {
    "title": "...",
    "title_similarity": 1.0,
    "venue": "...",
    "year": "...",
    "type": "...",
    "key": "...",
    "doi": "...",
    "url": "https://dblp.org/rec/..."
  }
}
```

The parent verifier then decides whether to call `match_conference_ranking` or `match_journal_ranking`.

## Caveats

- DBLP is strongest for computer science; absence from DBLP is not proof of non-acceptance.
- DBLP venue strings are often acronyms (`CVPR`, `NeurIPS`, `SIGCOMM`) rather than full names; ranking lookup must support acronym matching.
- DBLP search is not DOI-first; DOI queries may return no hits even when title queries work.
- DBLP may index both preprint (`CoRR`) and conference versions. Prefer DOI or exact title/year matches; treat `CoRR` as preprint unless another confirmed venue hit is selected.
- DBLP does not by itself prove main-track full-paper status. Keep workshop/short/demo/poster warnings from the parent verifier.

## Verification Checklist

- [ ] Query used `format=json` and `c=0`.
- [ ] Selected hit has DOI match or high title similarity.
- [ ] `CoRR` was not treated as confirmed journal/conference acceptance.
- [ ] DBLP venue was passed to local ranking CSV lookup.
- [ ] Ambiguous results produced warnings instead of a fabricated venue.
