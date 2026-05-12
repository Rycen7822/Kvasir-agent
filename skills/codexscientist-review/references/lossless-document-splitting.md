# Lossless document splitting audit

Use this reference when a substantial paper-like report is split into multiple documents and the original file is compressed into an index or routing document.

## Trigger

- User asks to split a long manuscript/report into `paper_main`, appendix, experiment protocol, implementation spec, related work, risk register, or similar companion files.
- User asks to keep the original source file compact after splitting.
- User asks to verify that split files did not lose content.

## Required workflow

1. Identify the authoritative pre-split source backup.
   - Prefer an explicit `before_*` backup created immediately before compression.
   - Record line count and SHA-256 of the source backup.

2. Parse the source into structural units before judging completeness.
   - Level-2 sections (`## ...`) are the first coverage unit.
   - Also count/check paragraph blocks, Markdown tables, display math blocks, and numbered reference lines.
   - For math-heavy Obsidian Markdown, whitespace-normalized exact matching is safer than fuzzy semantic matching.

3. Map each source section to a target split document.
   - Example mapping:
     - main paper: claim, contribution, concept boundary, paper skeleton, author decisions
     - related work: nearest-neighbor positioning and complete references
     - theory/method appendix: problem definition, protocols, diagnostics, propositions/lemmas
     - implementation spec: algorithm and intervention/conversion family
     - experiment protocol: experiment matrix, route, evidence gates
     - reviewer risk register: risk and defense section

4. If any content is only summarized in the split files, preserve a lossless carryover baseline, then separate it from the active manuscript surface.
   - Keep the original source document as an index if that was the user's preference.
   - For an intermediate no-loss checkpoint, use explicit markers such as:
     - `<!-- SOURCE-COMPLETE-CARRYOVER-START -->`
     - `<!-- SOURCE-COMPLETE-CARRYOVER-END -->`
   - Before treating split files as active paper documents, move those carryover blocks into an archive file such as `archive/legacy_full_source.md` or `archive_source_carryover.md`.
   - Active split documents should contain only current normative content plus a short archive pointer, e.g. `Legacy source blocks 已归档到 archive/legacy_full_source.md；本文件保留当前规范性内容。`
   - This avoids reviewer-facing contradictions from old definitions, old formulas, and obsolete terms while preserving a no-loss audit trail.

5. Write an audit report next to the split files.
   - Include source backup path, source hash, generated time, section-to-file allocation table, backups created, archive path, and final validation JSON.
   - If the project has a backup convention, put new manuscript backups under the designated backup directory rather than scattering timestamped backups among active documents.

6. Run final checks.
   - Missing level-2 source sections in the archive must be 0.
   - Missing source blocks above the chosen threshold in the archive should be 0.
   - Missing Markdown tables in the archive must be 0.
   - Missing display math blocks in the archive must be 0.
   - Missing numbered reference lines in the archive must be 0.
   - Active split documents must have `SOURCE-COMPLETE-CARRYOVER-START/END` count 0.
   - Active split documents must have old-term pollution count 0 for legacy method names, obsolete candidate-universe symbols, obsolete action tuples, and old probability notation.
   - Mechanical issues must be 0: forbidden phrases, obsolete symbols/claims, raw display math, math delimiter balance, table columns, duplicate headings outside fenced code.

7. Record a milestone/artifact if running inside CodexScientist or another durable workflow.

## Pitfalls

- A polished split summary is not a lossless split. Verify against the backup, not against the intended outline.
- Do not re-expand the compressed original source if the user asked it to become an index.
- Lossless carryover blocks are an intermediate preservation device, not the final active-document shape. Archive them before reviewer-facing or collaborator-facing cleanup.
- After archiving carryover, run two audits: source-to-archive coverage and active-document pollution checks.
- Ignore headings inside fenced code when checking duplicate headings; source title metadata can otherwise create false positives.
- Preserve pre-fill versions of each split file with a timestamped backup before adding carryover blocks; preserve later active-document cleanup backups in the project's backup directory when one exists.
