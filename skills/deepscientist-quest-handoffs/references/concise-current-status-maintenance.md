# Concise current-status maintenance for long-running research quests

Use when a quest's handoff/command/plan documents have grown too long or contain repeated stale status blocks, and the user asks for conservative cleanup rather than new experiments.

## Pattern

1. Treat active idea/protocol documents and validated run artifacts as source of truth. Do not delete experimental evidence, run directories, or historical long-form plans.
2. Create or refresh one short entry document, preferably `experiments/CURRENT_STATUS.md`, with:
   - current timestamp and quest root;
   - baseline gate / active stage;
   - current constraint such as no-sync/current-project-only;
   - authoritative reading order;
   - compact gate table (for example G0/G1/G2);
   - latest validated run path and key verification facts;
   - exact next boundary and explicit forbidden jumps.
3. Rewrite `AGENTS.md` as a short map, not a chronological run diary. Keep pointers to `CURRENT_STATUS.md`, current gate status, latest run, source-of-truth order, and no-sync constraints.
4. Keep long documents in their original roles:
   - formal command docs remain runnable command catalogs;
   - execution plans remain full protocol/history references;
   - add a top maintenance note and short-status pointer instead of appending more handoff prose.
5. Move misplaced latest status blocks into the proper section when safe (for example an E10.6 note should live before E11, not at the tail after later phases).
6. Replace stale "current next task" sections with a short pointer to `CURRENT_STATUS.md` and the true next boundary.
7. Validate after editing:
   - all key referenced paths exist;
   - every entry doc points to `CURRENT_STATUS.md`;
   - stale phrases from old handoffs are absent;
   - latest status block appears once and in the right section;
   - no files outside the user-authorized root were touched;
   - run a full quest-local git status, not only a scoped status, before recording artifacts. Artifact recording/checkpointing may commit all pending quest changes, so catch unrelated deletions or stale staged files first.
8. Record a milestone/report artifact for meaningful maintenance, including line counts and guardrails preserved. After artifact recording, re-check full git status and restore any unrelated accidental deletion immediately; do not leave it for a later cleanup turn.

## Pitfalls

- Do not convert partial/smoke/provenance records into final results while summarizing.
- Do not aggressively delete old protocol/history content from source-of-truth docs; use pointers and maintenance notes.
- If the user says not to touch a secondary copy, do not sync it even if earlier workflow memory says to sync AGENTS.
- Do not leave stale handoff paragraphs at the bottom of `AGENTS.md`; they are high-risk because future agents read them first.
