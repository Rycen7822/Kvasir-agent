---
name: codexscientist-strict-research
description: "Strict literature research mode for CodexScientist quests: broad candidate scouting first, reliability verification, conservative filtering, quest-local PDF download, then iterative bibliography reading notes before answering/writing."
version: 0.1.0
author: Codex Agent
---

> Codex adapter note: this stage skill is bundled for CodexScientist. Prefer the stable curated MCP `cs_*` tools for repeated CodexScientist state/status/context workflows. Load this support skill only when its stage is relevant. Runtime state lives under `<project>/CodexScientist/`.

# CodexScientist Strict Research Mode

Use this skill when the user asks the agent to **仔细调研论文、认真调研、谨慎确认、严格筛选、撰写综述、系统综述、literature review、survey、related work** or otherwise signals that references must be broad, verified, and conservatively selected before writing.

## Agent-managed activation

Strict research is **not** a keyword-only automatic mode. Heuristic routing may recommend this skill when it sees careful-research language, but the Codex agent must decide from the full user intent, task stakes, ambiguity, requested deliverable, and available time whether strict research is warranted. If selected, the agent should explicitly treat the quest as entering strict research and then follow the workflow below.

When the agent chooses strict research mode:

1. Work inside the active CodexScientist quest. If no quest exists, create one with `cs_new_quest`; for strict literature-map intent use `final_goal="literature_scout"` and a strict/literature `delivery_mode` so the quest starts on `strict-research` rather than the baseline anchor.
2. Call `cs_set_active_quest(stage="strict-research")` if re-entering an existing quest, then call `cs_strict_research_prepare` before reading papers deeply.
3. Broadly search for candidate papers first. Do **not** start detailed reading immediately.
4. Record or update every plausible candidate in `CodexScientist/quests/<quest>/reference/candidate_references.md` with title, DOI if known, URLs, source, and short reason using `cs_strict_research_upsert_candidate` (or append-only `cs_strict_research_record_candidate` only for first-pass raw capture).
5. When the candidate pool is large enough for the task complexity (or the user-specified count), run `cs_paper_reliability_verify` in small batches. After each paper, use the returned top-level `paper`, `tier`, `quality_flags`, `warnings`, and `reliability_card_path` fields; avoid dumping all JSON cards into chat unless needed.
6. After each small batch, immediately update the corresponding rows in `candidate_references.md` with `cs_strict_research_upsert_candidate(status=..., evidence_card=..., retain_reject_reason=...)` before starting the next batch.
7. After all candidates are verified and marked, clean `candidate_references.md`: delete papers that cannot be referenced (`verified-rejected`, `do_not_use`, desk-reject-only, unverifiable) unless the user explicitly requested retention; keep `verified-retained`, `user-specified-retained`, and clearly marked `needs-human-review` rows.
8. Apply the conservative filtering rules below. If retained papers are insufficient, continue scouting and repeat verification.
9. Download all retained papers with `cs_paper_fetch` into `reference/pdfs/`, recording `canonical_url`, `pdf_path`, `sha256`, `page_count`, `body_text_status`, and `official_resource_status` in the ledger. Prefer official arXiv/OpenReview/PMLR/PDF sources.
10. Call `cs_strict_research_init_bibliography` to create `reference/bibliography/` and the three required bibliography files.
11. Read retained papers one by one. After each paper, call `cs_record_literature_reading_note` with `paper_id`, `pdf_path`, `surfaces_read`, `sections_read`, `note`, `claim_routes`, and `status`, and update all relevant bibliography files before reading the next paper.
12. Only after all retained papers are read and bibliography files are updated should you answer the user, write a report, draft a paper, or perform the requested downstream task.

## Candidate file

`reference/candidate_references.md` is the broad-scouting ledger. Keep candidates even if not yet retained. Mark status as `candidate`, `verified-retained`, `verified-rejected`, or `user-specified-retained`.

## Filtering rules

### Preprints

Retain a preprint if any of the following is true:

- It was published more than one year ago and citation count is greater than 10.
- It was published within the last year and the authors are from top research institutions/labs; record the institutional evidence.
- The user explicitly指定/要求保留该论文.

### Conference papers

Retain an accepted conference paper if it is at least one of:

- CCF-A
- CCF-B
- CORE-A
- CORE-A*

If a conference submission was rejected:

- If it is not desk reject and has a preprint, evaluate it under the preprint rules.
- If it is desk reject, do not retain it unless the user explicitly指定.

### Journal papers

Retain an accepted journal paper if it is at least one of:

- CCF A
- CCF B
- 中科院 1区
- 中科院 2区
- JCR Q1
- JCR Q2

## Required bibliography files

Create these under `reference/bibliography/`:

1. `essential_reference_details.md` — for each retained paper, concise key information: finding/phenomenon, motivation, methodology, solved problem, conclusion. Keep each paper under 300 Chinese characters unless the user asks otherwise.
2. `reference_list.md` — writing guidance: which paper to cite when making specific claims, definitions, comparisons, motivations, limitations, or empirical statements.
3. `priority_reference_materials.md` — prioritized reading anchors: when using a paper's findings, opinions, or conclusions, which paper/section/paragraph/table/figure should be checked first.

## Reliability verifier

The bundled plugin skill `codexscientist:paper-reliability-verifier` is available for detailed rules. Use `cs_paper_reliability_verify` to run its verifier in the quest reference workspace. For large surveys, verify candidates in small batches and immediately write the summarized result back to `candidate_references.md` with `cs_strict_research_upsert_candidate`.

## Final response requirements

Report:

- quest id;
- `reference/` path;
- number of candidates collected;
- number retained and why;
- bibliography file paths;
- caveats such as unverifiable DOI, missing PDF, ambiguous venue, or insufficient retained count;
- completion time.
