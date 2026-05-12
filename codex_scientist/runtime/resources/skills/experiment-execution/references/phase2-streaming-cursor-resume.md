# Phase 2 streaming cursor resume guardrails

Use this note when a CodexScientist Phase 2 `main_100m`/full-budget runner has moved from a single bounded corpus sample to repeated resume chunks and needs to prove that later invocations advance through the streaming corpus instead of rereading the same local split/sample rows.

## Session-derived trigger

- A real bounded `main_100m` resume chunk runs successfully but is still far below the protocol token budget.
- A corpus manifest exists and the runner consumes manifest-backed records, yet resume semantics need auditing.
- Earlier chunks may have validated only invocation-local non-repetition. That is not enough for cross-invocation formal progress.

## Required runner semantics

1. Persist a per-corpus-family cursor in the run directory, for example `phase2_corpus_cursor.json` with keys such as `fineweb-edu`.
2. At resume start, load `cursor_before` from disk before selecting new records.
3. Select records starting at the persisted cursor, not always row 0 or the first local split/sample text.
4. After successful plan-compatibility checks and record selection, write `cursor_after` back to disk.
5. Keep an append-only audit log such as `phase2_corpus_consumption_records_history.jsonl` in addition to the current invocation's record file.
6. Include `cursor_before`, `cursor_after`, selected record indices, invocation token count, cumulative per-job token count, and remaining protocol tokens in `verification.json`/state artifacts.
7. Preserve side-effect ordering: if a resume is incompatible with the persisted plan/grid/limits, fail before updating cursor files, consumption records, job table, checkpoint, or eval artifacts.
8. Test both the positive resume path and the incompatible-plan guard. The guard test should assert that cursor/record side effects did not advance.

## Validation checklist after a controlled chunk

- `verification.all_checks_passed == true` for the bounded chunk.
- `cursor_after` is strictly ahead of `cursor_before` for the relevant corpus family.
- The invocation's consumption records correspond to the expected cursor range.
- The append-only history gained the expected records.
- `min_job_cumulative_tokens` advanced only by the tokenizer-counted tokens for this invocation.
- `writes_y_recover == false` and `g2_satisfied == false` remain explicit until the per-job protocol budget and formal candidate records are actually complete.
- `recover_target_recorcs.jsonl` does not exist unless formal `Y_recover` was truly written.

## Conservative reporting language

Use:

- "persisted streaming cursor validated for a bounded partial resume chunk"
- "cross-invocation corpus progress is now auditable, but formal 100M `Y_recover` remains pending"
- "G2 remains unsatisfied; E11/E12 remain blocked"

Avoid:

- treating a cursor-validated 2K/8K/32K chunk as paper-scale corpus consumption
- using aggregate token counts across jobs to satisfy a per-job budget
- saying the experiment plan is complete when `recover_target_recorcs.jsonl` is absent or `writes_y_recover=false`
