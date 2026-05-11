# ACL Anthology Accepted-Venue Detection Notes

Use for future extensions of `resources/skills/paper-reliability-verifier` when a paper may be in ACL/EMNLP/NAACL/EACL/AACL/COLING/CoNLL/TACL/CL, Findings, or ACL Anthology workshops.

## Docs and package

Docs read: <https://acl-anthology.readthedocs.io/py-v1.1.0/>

Installed package route in the user's `test` conda env:

```python
from acl_anthology import Anthology
anthology = Anthology.from_repo(verbose=False)
```

Important documented objects/fields:

- `Anthology.from_repo()` clones/updates official metadata and exposes `anthology.datadir`.
- `anthology.get("2022.acl-long.220")` returns a `Paper`.
- IDs are hierarchical: collection, volume, paper; e.g. `2022.acl` → `long` → `220`.
- `Paper` has `full_id`, `title`, `year`, `doi`, `bibkey`, `pdf`, `web_url`, `venue_ids`, `volume_id`, `collection_id`, `parent`.
- `MarkupText` titles/abstracts should be converted via `str(...)` or XML text extraction.
- `PDFReference.url` yields `https://aclanthology.org/<id>.pdf`.
- `Volume` has `title`, `year`, `venue_ids`, `web_url`, and track/volume information in its booktitle.
- `Venue` YAML records include `id`, `acronym`, `name`, `is_acl`, `is_toplevel`, `oldstyle_letter`.

## Implementation pattern that worked

Semantic source is the Python package, but for title-wide search prefer:

1. Call `Anthology.from_repo(verbose=False)` to locate the official local data directory.
2. Scan `data/xml/*.xml` for `<volume>` / `<paper>` records.
3. Read venue metadata from `data/yaml/venues/*.yaml`.
4. Match by exact normalized DOI first; otherwise require high normalized title similarity (used `>= 0.90`) and year match when known.
5. Return `accepted_publication` with `status=acl_anthology_confirmed` and an `acl_anthology` diagnostic object.

Reason for XML scan: the installed package can emit `SchemaMismatchWarning` when its bundled schema lags behind the latest downloaded data. Building global event/venue indices may parse the whole tree and fail on schema skew. XML scan avoids that while still using the official package-managed metadata.

## Venue mapping and Findings policy

- `acl`, `emnlp`, `naacl`, `eacl`, `aacl`, `coling`, `conll` → `conference`.
- `tacl`, `cl` → `journal`.
- ACL Anthology Findings is treated as a confirmed ACL-family publication track for this user. A Findings record can be `strong_evidence` when the ACL Anthology hit is independently confirmed and its parent ACL-family venue resolves to a top rank in local conference ranking.
- Implementation detail: detect Findings from `volume_title` / accepted venue text, suppress the generic `findings_or_non_main_track` demotion only for `accepted_publication.status = acl_anthology_confirmed`, and map the ranking lookup to the parent ACL-family venue/acronym rather than ranking the literal Findings booktitle.
- Preserve non-main-track caveats for workshop, short, demo, student research workshop, tutorials, shared task, poster, companion, and extended abstract; these remain not main-track full-paper evidence.

## Verified examples

From `resources/skills/paper-reliability-verifier`:

```bash
/home/xu/miniconda3/envs/test/bin/python scripts/verifier.py \
  --title "Learned Incremental Representations for Parsing" \
  --year 2022
```

Result: `acl_anthology_confirmed`, ACL, conference, local ranking CCF A / CORE A*.

```bash
/home/xu/miniconda3/envs/test/bin/python scripts/verifier.py \
  --title "IAG: Induction-Augmented Generation Framework for Answering Reasoning Questions" \
  --year 2023
```

Result: `acl_anthology_confirmed`, EMNLP, local ranking CCF B / CORE A*.

```bash
/home/xu/miniconda3/envs/test/bin/python scripts/verifier.py \
  --title "Named Entity Recognition Under Domain Shift via Metric Learning for Life Sciences" \
  --year 2024
```

Result: `acl_anthology_confirmed`, NAACL, local ranking CCF B / CORE A.

DBLP fallback was preserved: ResNet/CVPR still returned `dblp_confirmed`.
