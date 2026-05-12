# Paper-Like Idea Revision From External Researcher Feedback

Use this reference when a user provides a substantial research memo and asks to revise an existing idea/report as if it were the paper owner's manuscript.

## Revision pattern

1. Treat the external memo as a concrete manuscript revision request, not a discussion prompt.
2. Read the current draft first; map memo items to existing sections.
3. Prefer section-level patches to full rewrites. Patch title/abstract/problem definition first, then method score, baselines, experiment matrix, risks/gates, references.
4. Convert advisory language into first-author claims and protocols. Avoid "建议/should/可能需要" in the manuscript unless explicitly writing future limitations.
5. Preserve explicit user style constraints as mechanical checks: forbidden phrases, language choice, formula rendering, reference continuity, and brevity. If the user lists banned phrasings (e.g. contrastive "不是/而是" patterns or "建议/应该/不能/不要" advisory terms), scan for those exact strings after editing and remove them from manuscript prose.
6. Apply each memo item by first looking for an existing paragraph/table/formula to revise; add new material only when the current document lacks a required definition, table column, metric, or protocol. This prevents reviewer-response bloat.
7. When the memo names new papers/baselines, fetch and verify primary PDFs before editing related-work/baseline claims when the claim depends on details not present in the memo. If the user supplied explicit venue/status corrections and the task is manuscript revision, update the manuscript conservatively from the memo and leave deep paper fetching for a separate literature pass.
8. In CodexScientist quest work, use the quest-local retrieval and durability surfaces (`cs_paper_fetch`, `cs_artifact_record`, `cs_memory_write`, and when shell work is required `cs_bash_exec` if available for the active stage) so the evidence and route remain auditable. For `cs_artifact_record`, use canonical artifact kinds such as `idea`, `decision`, `milestone`, etc.; do not invent narrow kinds like `idea_revision`. If a `report` record returns `status: semantically_equivalent`, `suppressed: true`, or points to an unrelated older artifact, do not claim that as the current checkpoint; retry with a canonical `milestone` checkpoint containing paths, revision id, checksum, validation summary, and completion time, then read the artifact JSON back. If using `decision`, include a valid `action` from the CodexScientist schema plus `verdict` and `reason`.
9. After editing, reread the full document and run scripted checks for:
   - forbidden phrases and obsolete claim terms;
   - when the user bans contrastive or minimizing constructions, scan both the exact banned Chinese strings and their nearby English/Chinese residues such as `only` and `只`; remove residues from active manuscript prose, not from archived backups;
   - Obsidian-friendly display math (`$$...$$`, avoid raw `\\[` / `\\]` when the user requests it);
   - inline math delimiter balance (`\\(` count equals `\\)` count per line);
   - table column consistency; in Markdown tables, inline math containing literal `|` breaks column parsing, so write norms/cardinalities as `\\lvert ... \\rvert` or `\\left\\|...\\right\\|` rather than `|...|` inside table cells;
   - overlong non-table lines / duplicated sections / stale terminology;
   - reference numbering continuity;
   - downloaded PDF presence, `%PDF` header, byte size, hash, and page count when papers were fetched.
10. For repeated external-researcher revision passes on a split idea bundle, use an initial/final audit pattern: make timestamped backups under `idea/backup/`, run an initial hygiene scan before editing, patch only the small affected sections, reread the changed ranges, then run a final audit that records requirement hits, mechanical issue count, line counts, SHA-256 hashes, and source-to-archive coverage. If the final scan forces a cleanup in an additional active file outside the original memo list, immediately create a matching pre-cleanup backup for that file with the same revision stamp before or right after the small cleanup. When the source document has become an index, update the index version/source map only for route-level changes; keep formulas, baseline definitions, thresholds, and risks in their split documents. Treat audit reports as an append-only evidence chain: do not delete or overwrite older `active_doc_*audit_*.md` / `initial_hygiene_*.md` files during cleanup or checkpointing. Keep `idea/` root reserved for active idea Markdown files; put audit reports in `idea/audits/`, backups in `idea/backup/`, and legacy/source carryover in `idea/archive/`. If the root becomes cluttered, create the missing directory, move files with Git-tracked renames, update the index document's directory map and path text, and write any new directory-hygiene audit inside `idea/audits/` so the root remains clean.
11. For CodexScientist `cs_artifact_record` checkpoints, put the decisive validation facts directly in `summary` as well as any structured fields. Some artifact schemas may not persist arbitrary `metadata` or `paths`; read the JSON back and retry with a canonical `milestone` summary if the first artifact omits checksum, paths, or completion time. If the artifact response reports `committed: false` or leaves the repository dirty, create an explicit local git checkpoint after recording the milestone, unless the user has forbidden commits. After any artifact-managed or manual checkpoint, inspect `git status --short` for unintended deletions or renames of prior audit reports; if present, restore them from the previous commit and add a small follow-up checkpoint before reporting completion.
12. If the memo asks to split a large idea/report into paper components, create the requested files as concise derived documents in the same target directory while also revising the source draft. Typical split targets are `paper_main.md`, `appendix_theory_and_methods.md`, `experiment_protocol.md`, `implementation_spec.md`, `related_work_notes.md`, and `reviewer_risk_register.md`; keep source-of-truth claims consistent across all split files. If a no-loss split previously inserted legacy carryover blocks into active documents, move those blocks to an archive file before reviewer-facing cleanup, and leave only a one-sentence archive pointer in each active document.
13. After a split, validate both the revised source and all current active Markdown files, excluding timestamped backups and archive files from active-doc style checks. In addition to style/math/table checks, run coverage checks for the memo's required symbols, scope boundaries, model lists, figure counts, appendix/main separation, and absence of legacy terms in active documents. Record line counts and SHA-256 hashes for the source and split documents in the milestone summary.

## Reviewer-memo pitfall checklist

When a memo says the idea has target leakage, baseline category errors, or infeasible experiment scale, update the manuscript structure rather than adding defensive prose:

- Split score variants when a feature uses a stronger information surface, e.g. `no-forward` versus `forward`, and add a leakage table listing labels, converted-forward CE, held-out targets, and training outcomes.
- Separate score-side calibration stress proxies from held-out evaluation targets; rename metrics when needed so the score cannot be read as the target itself.
- Distinguish selector baselines from conversion/initialization families and from per-input routing/search methods. Use a selector × conversion matrix when a method contributes a conversion recipe rather than a static selector.
- Put direct-trial baselines into the main comparison when the proposed score can be interpreted as a complicated version of that trial.
- Funnel expensive targets: full candidate set for frozen conversion, selector-selected subset for low-budget recovery, and final subset for expensive elasticity/retrofit.
- If a required-term check reports a miss, inspect spelling and math escaping before editing; `\\mathrm{Regret}` and `Regret` may both satisfy the writing requirement while differing from a literal script pattern.

## Example outcome shape

A strong revision should leave:

- a backup of the prior draft;
- the revised manuscript/report;
- downloaded/verified papers under the project reference directory when requested;
- a concise artifact/memory record if working in CodexScientist;
- a final report with exact paths, checksum/line-count checks, reference count, and completion time when the user expects completion time.
