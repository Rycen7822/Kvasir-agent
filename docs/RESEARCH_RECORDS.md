# Project research records

Keep original papers, notes, ideas and reports at their existing project paths. A research JSON document describes one source, idea, candidate, claim, review or negative result. It has a stable record ID, hashed content, typed metadata and exact revision references. Load only the matching type schema when creating a document: [source](specs/research-source.schema.json), [idea](specs/research-idea.schema.json), [candidate](specs/research-candidate.schema.json), [claim](specs/research-claim.schema.json), [review](specs/research-review.schema.json), [negative result](specs/research-negative_result.schema.json). The [idea example](specs/research.example.json) shows the shared envelope; the complete union is a validator artifact, not required reading.

Explicitly register a document or rebuild its derived index:

```sh
python /path/to/plugin/scripts/ka_admin.py research-register --project /absolute/project --spec-path research/idea.json
python /path/to/plugin/scripts/ka_admin.py research-index --project /absolute/project
```

These operations require an already initialized project. They do not initialize, migrate or inject context. Registration stores immutable revisions under `Kvasir-agent/research/records/ID/DIGEST.json`; the original content file is not moved. Same document reuses its revision. If index writing fails, the record survives with `derivation_status=partial`; use research-index to recover. A new revision preserves older records.

The index lives at `Kvasir-agent/research/index.json`. It includes content and history paths and explicit migration path_map entries with legacy_unverified trust. Use the host's normal search/read tools to locate titles, IDs, ideas, negative results and archived history. The index is derived navigation, not the evidence itself. Registration and index rebuild are explicit actions.

Check current research records with CheckSpec v2:

```json
{"schema_version": 2, "target": "research", "record_ids": ["hypothesis-1"]}
```

The existing ka_evidence_check saves hash/version/dependency results and limitations. Changes to content, candidate inputs or review targets become stale. A newer dependency revision is visible as superseded; original historical revisions remain readable. Referenced runs are checked rather than trusted by their labels. Missing dependencies and unresolved locators stay explicit.

Source records retain exact version and acquisition coverage, queries and locators. Line excerpts are checked against saved UTF-8 bytes; PDF/page locators remain unresolved without a suitable reader. Abstract-only, truncated, unavailable or changed-query states are limitations, not independent scientific support. Record acquisition failures with a local receipt as content rather than inventing an experiment.

Candidate records pin code/config files, method identity, parent revisions and rationale. RunSpec v2 can bind candidate_path; the full candidate document is part of request identity and its input files are checked before and after execution. Review records bind actual saved target bytes and a real feedback content file. Reviewer and outcome are declarations; a version check does not certify review quality or scientific truth. Approved reviews with unresolved issues are rejected.

Research workflow templates are loaded when useful: [hypotheses](research/templates/hypothesis.md), [analogy](research/templates/analogy.md), [comparison](research/templates/comparison.md), [literature receipt](research/templates/literature-receipt.md), [review](research/templates/review.md), [negative result](research/templates/negative-result.md), [stopping rules](research/templates/stop-rule.md). Codex/Pi performs reasoning, retrieval and independent review, using existing run/check tools for experiments.
