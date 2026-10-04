# Project research records

Keep original papers, notes, ideas and reports at their existing project paths. A research JSON document describes one source, idea, candidate, claim, review or negative result. It has a stable record ID, a content path, typed metadata and ordinary revision references such as `v1`. No content, input or locator hashes are required. Load only the matching type schema when creating a document: [source](specs/research-source.schema.json), [idea](specs/research-idea.schema.json), [candidate](specs/research-candidate.schema.json), [claim](specs/research-claim.schema.json), [review](specs/research-review.schema.json), [negative result](specs/research-negative_result.schema.json). The [idea example](specs/research.example.json) shows the shared envelope; the complete union is a validator artifact, not required reading.

Explicitly register a document or rebuild its derived index:

```sh
python /path/to/plugin/scripts/ka_admin.py research-register --project /absolute/project --spec-path research/idea.json
python /path/to/plugin/scripts/ka_admin.py research-index --project /absolute/project
```

These operations require an already initialized project. Each explicit registration automatically creates `v1`, `v2`, etc. under `Kvasir-agent/research/records/ID/vN.json`. The corresponding `ID/vN/` directory holds copies of the research content, source locator materials and review target. Original files remain in place; registering a revised body requires no hash maintenance or metadata change. Registration does not copy all candidate code or datasets. If index writing fails, the saved version survives with `derivation_status=partial`; use research-index to recover. Older versions remain readable. Legacy hash-named records are read in place without recalculating their hashes; they may lack saved material copies, which is reported as a limitation.

The index lives at `Kvasir-agent/research/index.json`. It includes content and history paths and explicit migration path_map entries with legacy_unverified trust. Use the host's normal search/read tools to locate titles, IDs, ideas, negative results and archived history. The index is derived navigation, not the evidence itself. Registration and index rebuild are explicit actions.

Check current research records with CheckSpec v2:

```json
{"schema_version": 2, "target": "research", "record_ids": ["hypothesis-1"]}
```

The existing ka_evidence_check inspects saved materials, exact dependency references and available run records. A new parent version or editing the current content does not invalidate a pinned historical version. Missing dependencies, unavailable copies, invalid excerpts and unresolved locators stay explicit. The check returns a completed report even when it finds issues; it does not recursively hash inputs or certify unchanged bytes.

Source records retain exact version and acquisition coverage, queries and locators. Line excerpts are checked against saved UTF-8 bytes; PDF/page locators remain unresolved without a suitable reader. Abstract-only, truncated, unavailable or changed-query states are limitations, not independent scientific support. Record acquisition failures with a local receipt as content rather than inventing an experiment.

Candidate records declare code/config paths and optional versions, method identity, parent revisions and rationale. RunSpec v2 can bind candidate_path; the launch saves the candidate document and checks method/binding identities, without requiring latest parents or byte checks before and after execution. Candidate paths and declared versions do not prove which bytes the program used. Review registration preserves its target and feedback content. Reviewer and outcome remain declarations; an approved review with unresolved issues is recorded and flagged during explicit review. A saved version does not certify review quality or scientific truth.

Research workflow templates are loaded when useful: [hypotheses](research/templates/hypothesis.md), [analogy](research/templates/analogy.md), [comparison](research/templates/comparison.md), [literature receipt](research/templates/literature-receipt.md), [review](research/templates/review.md), [negative result](research/templates/negative-result.md), [stopping rules](research/templates/stop-rule.md). Codex/Pi performs reasoning, retrieval and independent review, using existing run/check tools for experiments.
