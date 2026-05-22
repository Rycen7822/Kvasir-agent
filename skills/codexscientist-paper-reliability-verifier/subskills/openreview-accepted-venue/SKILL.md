---
name: openreview-accepted-venue
description: Use when paper-reliability-verifier needs to verify acceptance and presentation type for OpenReview-hosted venues such as ICLR, TMLR, COLM, or related workshops before local rank lookup.
version: 0.1.0
author: Codex Agent
license: MIT
metadata:
  hermes:
    tags: [openreview, iclr, publications, venue, decision, reliability, paper-ranking]
    related_skills: [paper-reliability-verifier]
---

# OpenReview Accepted Venue Detection

## Scope

This is an embedded support skill for `paper-reliability-verifier`, same level as `acl-anthology-accepted-venue` and `dblp-accepted-venue`.

Use it when a paper may have been submitted to or accepted by an OpenReview-hosted venue, especially:

- ICLR (`ICLR.cc/<year>/Conference`);
- TMLR;
- COLM;
- UAI or OpenReview-hosted workshops;
- any venue where the OpenReview group / forum URL is known.

This skill answers two separate questions:

1. **Acceptance status**: whether OpenReview metadata indicates the paper was accepted by the venue.
2. **Presentation type**: oral / spotlight / poster / accepted-with-unknown-presentation, when the venue exposes this information.

Do not conflate these layers. A poster can still be an accepted conference paper; oral/spotlight/poster is a presentation label, not the venue identity.

## Documentation Read

Primary guide:

```text
https://docs.openreview.net/how-to-guides/data-retrieval-and-modification/how-to-get-all-notes-for-submissions-reviews-rebuttals-etc
```

Key points from the docs:

- Current venues use API 2 through `openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")`.
- Some older venues, especially before migration to API 2, still require API 1 patterns.
- API 2 uses `client.get_all_notes(...)` for submissions, reviews, rebuttals, comments, meta-reviews, and decisions.
- API 2 accepted submissions can be retrieved with:

```python
client.get_all_notes(content={"venueid": "ICLR.cc/2024/Conference"})
```

- `content.venueid` distinguishes accepted, withdrawn, rejected, and desk-rejected submissions. Accepted submissions normally use the original venue ID.
- Replies such as decisions can be included with `details="replies"` and filtered by invitations ending in `Decision`.
- API 1 venues often use:

```python
client.get_all_notes(
    invitation="<Venue/ID>/-/Blind_Submission",
    details="directReplies,original",
)
```

Then decisions are direct replies whose invitation ends in `Decision`.

## Credentials

The local verifier loads credentials, if present, from:

```text
$CODEX_HOME/secrets/openreview.env
```

Expected variables:

```text
OPENREVIEW_USERNAME=...
OPENREVIEW_PASSWORD=...
```

Never print these values. Public OpenReview metadata often works without credentials, but credentials can help with venues that require login or rate limits.

## API 2 Query Pattern

Known venue ID example:

```python
import openreview

client = openreview.api.OpenReviewClient(
    baseurl="https://api2.openreview.net",
    username=os.getenv("OPENREVIEW_USERNAME"),
    password=os.getenv("OPENREVIEW_PASSWORD"),
)

venue_id = "ICLR.cc/2024/Conference"
accepted_submissions = client.get_all_notes(
    content={"venueid": venue_id},
    details="replies",
)
```

For each note, read content values with API-2 compatibility:

```python
def get_value(content, key):
    v = content.get(key)
    if isinstance(v, dict) and "value" in v:
        return v["value"]
    return v
```

Important fields:

- `content.title`
- `content.venueid`
- `content.venue`
- `note.id`, `note.forum`, `note.number`
- replies whose invitation ends with `Decision`
- decision note `content.decision`

## API 1 Query Pattern

For older venues:

```python
client = openreview.Client(
    baseurl="https://api.openreview.net",
    username=os.getenv("OPENREVIEW_USERNAME"),
    password=os.getenv("OPENREVIEW_PASSWORD"),
)

submissions = client.get_all_notes(
    invitation=f"{venue_id}/-/Blind_Submission",
    details="directReplies,original",
)
```

Then:

- inspect `submission.details["directReplies"]`;
- keep direct replies whose `invitation` ends with `Decision`;
- read `decision_note["content"]["decision"]`;
- if accepted, use `submission.details["original"]` as the public/original submission metadata when available.

## Matching Rules

OpenReview is not a global publication registry. Prefer using it when the venue ID is known or strongly inferred.

Recommended sequence:

```text
paper title / DOI / arXiv ID
→ DBLP / Crossref / OpenAlex / local knowledge suggests ICLR/TMLR/COLM/OpenReview-hosted venue
→ query OpenReview with explicit venue_id
→ parse acceptance and presentation type
→ pass accepted venue to local ranking CSV lookup
```

Accept a hit only when:

1. normalized title similarity is high enough, default `>= 0.92`; and
2. OpenReview evidence indicates acceptance through `content.venueid`, `content.venue`, or Decision note.

Do not guess if the best title match is weak. Return `openreview_not_found_or_ambiguous` and keep top hits as diagnostics.

If a matched paper has a Decision note or venue label indicating rejection, return `openreview_not_accepted` and do **not** run local venue ranking as accepted evidence.

## Presentation Type Classification

OpenReview has no universal `presentation_type` schema. Parse multiple evidence strings:

- `Decision` note, e.g. `Accept (poster)`, `Accept: Oral`;
- final submission `content.venue`, e.g. `ICLR 2024 poster`, `ICLR 2024 oral`;
- page/venue labels where available.

Classification:

```text
contains oral      -> oral
contains spotlight -> spotlight
contains poster    -> poster
contains accept    -> accepted_unknown_presentation_type
contains reject    -> rejected
otherwise          -> null
```

## Output Contract to Parent Verifier

Return an `accepted_publication`-compatible object:

```json
{
  "status": "openreview_confirmed | openreview_not_accepted | openreview_not_found_or_ambiguous",
  "venue_name": "International Conference on Learning Representations",
  "venue_type": "conference",
  "acronym": "ICLR",
  "evidence_source": "OpenReview accepted submissions: accepted_title_match",
  "interface_version": "accepted-publication-v1",
  "openreview": {
    "openreview_id": "...",
    "forum": "...",
    "number": 7,
    "title": "...",
    "title_similarity": 1.0,
    "venueid": "ICLR.cc/2024/Conference",
    "venue_label": "ICLR 2024 oral",
    "decision_notes": ["Accept (oral)"],
    "accepted": true,
    "presentation_type": "oral",
    "url": "https://openreview.net/forum?id=..."
  }
}
```

The parent verifier then decides whether to call `match_conference_ranking` or `match_journal_ranking`.

## CLI Usage

Explicit venue query:

```bash
python scripts/verifier.py \
  --title "Graph Neural Networks for Learning Equivariant Representations of Neural Networks" \
  --year 2024 \
  --openreview-venue-id ICLR.cc/2024/Conference
```

Disable OpenReview:

```bash
python scripts/verifier.py --title "paper title" --no-openreview
```

For batch usage without specifying every command, set:

```bash
export OPENREVIEW_VENUE_IDS="ICLR.cc/2024/Conference,ICLR.cc/2023/Conference"
```

## Common Pitfalls

- Do not use OpenReview alone to search all possible publication venues.
- Do not assume oral/poster is a standard field; parse decision and final venue labels.
- Do not treat withdrawn/rejected/desk-rejected venue IDs as accepted evidence.
- Do not treat title similarity below threshold as confirmation.
- Do not expose OpenReview username/password in logs, JSON output, or docs.
- Do not infer CCF/CORE/中科院分区/JCR rank from OpenReview. Ranking still comes from local CSV snapshots.

## Verification Checklist

- [ ] Venue ID is explicit or strongly inferred.
- [ ] API 2 `content={"venueid": venue_id}` route was attempted for current venues.
- [ ] API 1 `Blind_Submission` + `directReplies,original` route is available for old venues.
- [ ] Selected hit has high title similarity.
- [ ] Decision note and/or final `venue` label was parsed.
- [ ] Acceptance and presentation type are separate fields.
- [ ] Rejected/withdrawn/desk-rejected records are not ranked as accepted venue evidence.
- [ ] Local ranking CSV lookup is used after acceptance is confirmed.
