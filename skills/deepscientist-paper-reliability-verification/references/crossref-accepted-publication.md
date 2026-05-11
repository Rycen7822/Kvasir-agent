# Crossref accepted-publication fallback notes

Use this reference when maintaining or extending Crossref support in the local paper reliability verifier.

## API documentation checked

- Swagger UI: `https://api.crossref.org/swagger-ui/index.html`
- Machine-readable Swagger spec: `https://api.crossref.org/swagger-docs`
- Main endpoints used by the verifier:
  - `GET https://api.crossref.org/v1/works/{doi}`
  - `GET https://api.crossref.org/v1/works?query.title=...`

Useful `/works` parameters observed in the Swagger/API behavior:

- `rows`, `sort`, `order`, `offset`, `cursor`
- `query`, `query.title`, `query.bibliographic`
- `filter`, e.g. `from-pub-date:YYYY-01-01,until-pub-date:YYYY-12-31`
- `select`
- `mailto`

Important compatibility detail: `select=subtype` is not accepted by the Crossref `/works` route in this workflow and can produce a 400. Do not include `subtype` in the `select` field list.

## Implementation pattern

Crossref should remain a conservative fallback after higher-confidence acceptance routes:

```text
explicit user confirmation > OpenReview > ACL Anthology > DBLP > Crossref Works > metadata-only unconfirmed
```

Recommended functions/behaviors:

1. Keep DOI lookup robust: if `/works/{doi}` returns no JSON or 404, return a structured error such as `{"_error": "crossref_not_found"}` rather than dereferencing `None`.
2. Use polite-pool metadata when available:
   - env var: `CROSSREF_MAILTO`
   - add `mailto` query parameter
   - add User-Agent suffix like `(mailto:...)`
3. Add title-only search with `query.title`, conservative row count, and publication-year filter when a year is supplied.
4. Require high normalized title similarity; when year is supplied, require year match for accepted-publication confirmation.
5. Preserve Crossref summary fields under `accepted_publication.crossref`, including DOI/title/year/type/container-title/event/publisher/URL/ISSN/ISBN/relations/updates/`is-referenced-by-count`.
6. For title-only cases, if the separate citations object lacks `crossref` but the accepted Crossref summary has `is_referenced_by_count`, backfill `citations.crossref` from the accepted result.

## Conservative acceptance rules

Confirm only when Crossref metadata clearly indicates a formal journal/proceedings publication:

- `journal-article` plus `container-title` => journal confirmation.
- `proceedings-article` => conference/proceedings confirmation.
- `event.name` can strengthen conference/proceedings evidence.
- `posted-content`, arXiv/bioRxiv/medRxiv containers, or obvious preprint containers => preprint-only / unclassified, not accepted publication.
- Unsupported types such as `book-chapter` should remain ambiguous unless another higher-confidence source confirms acceptance.

Suggested statuses:

```text
crossref_confirmed
crossref_preprint_or_unclassified
crossref_not_found_or_ambiguous
```

Expose a CLI opt-out such as `--no-crossref` for testing or when the caller wants to disable this fallback.

## Venue ranking pitfall discovered

When Crossref confirms short journal names, do not use substring matching for local journal ranking. Example: `Nature` must not match `Nature Computational Science` merely because one normalized title contains the other.

Journal ranking lookup should prefer:

1. exact normalized journal title;
2. exact acronym/short-title where the local data explicitly supports it;
3. very conservative fuzzy matching only.

Do not use broad `query in candidate` or `candidate in query` substring logic for journal names.

## Minimal regression tests to keep

- Journal article via Crossref confirms `venue_type = journal`.
- Proceedings article via Crossref confirms conference/proceedings and extracts parenthetical acronym such as `(CVPR)`.
- DBLP miss can route to Crossref fallback.
- Preprint/posted-content/arXiv-like record does not confirm formal acceptance.
- Unsupported Crossref work type remains ambiguous.
- Title-only Crossref fallback backfills `citations.crossref`.
- Short journal title does not substring-match a longer local ranking row.

## Verified example

Title-only fallback example:

```bash
python scripts/verifier.py \
  --title "Deep Residual Learning for Image Recognition" \
  --year 2016 \
  --no-acl-anthology \
  --no-dblp
```

Expected result shape:

```text
accepted_publication.status = crossref_confirmed
accepted_publication.venue_name = 2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)
accepted_publication.acronym = CVPR
venue.ccf_rank = A
venue.core_rank = A*
citations.crossref = <Crossref is-referenced-by-count value>
tier = strong_evidence
```
