---
name: acl-anthology-accepted-venue
description: Use when paper-reliability-verifier needs to infer whether an NLP/CL paper is indexed in ACL Anthology and extract its ACL/EMNLP/NAACL/EACL/AACL/TACL publication venue before local rank lookup.
version: 0.1.0
author: Codex Agent
license: MIT
metadata:
  hermes:
    tags: [acl-anthology, nlp, publications, venue, reliability, paper-ranking]
    related_skills: [paper-reliability-verifier]
---

# ACL Anthology Accepted Venue Detection

## Scope

This is an embedded support skill for `paper-reliability-verifier`, same level as `subskills/dblp-accepted-venue/SKILL.md`. Use it when a paper may belong to venues indexed by ACL Anthology, especially:

- ACL, EMNLP, NAACL, EACL, AACL, COLING, CoNLL;
- Findings of ACL/EMNLP/NAACL/EACL/AACL;
- TACL or Computational Linguistics;
- ACL Anthology workshops and shared-task proceedings.

Its job is narrow:

1. Use the `acl-anthology` Python package to locate/download the official ACL Anthology metadata repository.
2. Search local ACL metadata by DOI or conservative normalized title/year match.
3. Extract the Anthology ID, URL/PDF URL, volume title, venue ID/acronym/name, and paper metadata.
4. Fill the parent verifier's `accepted_publication` object.
5. Let the parent verifier use local `paper_ranking/*.csv` for CCF/CORE/中科院分区/JCR ranking.

This skill answers “is this paper present in ACL Anthology and under what ACL venue/volume?” It does **not** replace local ranking snapshots.

## Documentation Read

Primary docs:

```text
https://acl-anthology.readthedocs.io/py-v1.1.0/
```

Relevant documented API concepts:

- Install with `pip install acl-anthology` on Python 3.10+.
- Instantiate from the official repository:

```python
from acl_anthology import Anthology
anthology = Anthology.from_repo()
```

- The first call clones/updates roughly 120 MB of metadata; later calls reuse/update the local checkout.
- Instantiate from a local data directory when needed:

```python
anthology = Anthology(datadir="/path/to/acl-anthology/data")
```

- `anthology.get("2022.acl-long.220")` returns a `Paper`; IDs are hierarchical: collection, volume, paper.
- `anthology.get("2022.acl")` returns a `Collection`; `anthology.get("2022.acl-long")` returns a `Volume`.
- `Paper` metadata includes `full_id`, `full_id_tuple`, `title`, `authors`, `year`, `doi`, `bibkey`, `pages`, `abstract`, `pdf`, `web_url`, `venue_ids`, `volume_id`, `collection_id`, and `parent`.
- `MarkupText` fields such as title/abstract should be converted with `str(...)` to strip Anthology XML markup.
- `PDFReference.url` gives `https://aclanthology.org/<id>.pdf`; `Paper.web_url` gives the public paper page.
- `Volume` metadata includes `full_id`, `title`, `year`, `venue_ids`, `venues()`, `web_url`, and `get_events()`.
- `Event` objects are addressed as `{venue}-{year}`, e.g. `acl-2022`, and can group main conference, Findings, workshops, and colocated events.
- `Venue` metadata includes `id`, `acronym`, `name`, `is_acl`, `is_toplevel`, `url`, and associated volume IDs.

## Implementation Notes for Codex

The preferred semantic route is the documented Python package:

```python
from acl_anthology import Anthology
anthology = Anthology.from_repo(verbose=False)
paper = anthology.get("2022.acl-long.220")
```

For verifier-wide title search, the current implementation uses the package to locate `anthology.datadir`, then scans the official XML files under `data/xml`. This is intentional because package-level global indices such as venues/events may require loading the entire latest metadata tree and can fail if the installed `acl-anthology` schema is older than the downloaded data. XML scanning preserves the documented data model while avoiding brittle full-index construction.

If a caller already has an Anthology ID, use `anthology.get(id)` directly. If the caller only has a title or DOI, scan XML records.

## Matching Rules

Prefer explicit user-provided accepted venue over ACL Anthology. Use ACL Anthology before DBLP when the paper is likely NLP/CL or when title/DOI search in ACL metadata succeeds.

Accept a hit only when one of these is true:

1. DOI matches exactly after normalization.
2. Normalized title similarity is high enough, default `>= 0.90`, and year matches when year is known.
3. Normalized title similarity is high enough and it is the best hit when year is unknown.

If hits are low-similarity or ambiguous, do not guess. Return `acl_anthology_not_found_or_ambiguous` and keep the top few hits for diagnostics. Absence from ACL Anthology is not evidence that the paper was not published elsewhere.

## Venue Type Mapping

Use volume venue metadata:

- venue IDs `acl`, `emnlp`, `naacl`, `eacl`, `aacl`, `coling`, `conll`, etc. -> `conference`;
- `tacl` and `cl` -> `journal`;
- workshop/shared-task volumes are still `conference`-like proceedings for indexing, but must carry non-main-track warnings from the volume title;
- ACL Anthology `Findings` volumes are accepted ACL-family publication records; map them to their parent ACL/EMNLP/NAACL/EACL/AACL/COLING/CoNLL venue for ranking;
- `short`, `demo`, `student research workshop`, `system demonstrations`, `tutorial abstracts`, `workshop`, `shared task`, `poster`, and `extended abstract` are not main-track full-paper evidence.

For ranking lookup, pass:

- `venue_name`: the full venue name from venue YAML when available, e.g. `Annual Meeting of the Association for Computational Linguistics`;
- `acronym`: ACL/EMNLP/NAACL/EACL/AACL/TACL;
- `venue_type`: `conference` or `journal`.

## Output Contract to Parent Verifier

Return an `accepted_publication`-compatible object:

```json
{
  "status": "acl_anthology_confirmed | acl_anthology_not_found_or_ambiguous",
  "venue_name": "Annual Meeting of the Association for Computational Linguistics",
  "venue_type": "conference",
  "acronym": "ACL",
  "evidence_source": "ACL Anthology local metadata: title_year_match",
  "interface_version": "accepted-publication-v1",
  "acl_anthology": {
    "title": "Learned Incremental Representations for Parsing",
    "title_similarity": 1.0,
    "year": "2022",
    "doi": "10.18653/v1/2022.acl-long.220",
    "anthology_id": "2022.acl-long.220",
    "bibkey": "kitaev-etal-2022-learned",
    "url": "https://aclanthology.org/2022.acl-long.220/",
    "pdf_url": "https://aclanthology.org/2022.acl-long.220.pdf",
    "venue_id": "acl",
    "venue_acronym": "ACL",
    "venue_name": "Annual Meeting of the Association for Computational Linguistics",
    "volume_title": "Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)",
    "source_xml": "2022.acl.xml"
  }
}
```

The parent verifier then decides whether to call `match_conference_ranking` or `match_journal_ranking`.

## Operational Caveats

- The package may emit `SchemaMismatchWarning` if its bundled schema differs from the latest downloaded data; this is not automatically fatal for lookup.
- Avoid building global venue/event/person indices unless needed; they can require parsing all XML files.
- ACL Anthology includes workshops and Findings. Findings is strong evidence of publication and can be strong venue evidence after parent-venue rank lookup; workshops still need non-main-track caveats.
- Use the volume title and Anthology ID to preserve track information.
- Do not scrape the website for metadata when the package/local XML data already provides it.

## Verification Checklist

- [ ] `acl-anthology` package can instantiate `Anthology.from_repo()` or `ACL_ANTHOLOGY_DATA_DIR` points to a valid `data/` directory.
- [ ] Selected hit has DOI match or high title similarity.
- [ ] Year was checked when known.
- [ ] `venue_name`, `acronym`, and `venue_type` were mapped into `accepted_publication`.
- [ ] ACL Anthology Findings signals from `volume_title` were mapped to the parent venue for ranking; workshop/short/demo/non-main-track signals were preserved as warnings.
- [ ] The accepted venue was passed to local ranking CSV lookup; ranking was not inferred from ACL Anthology alone.
