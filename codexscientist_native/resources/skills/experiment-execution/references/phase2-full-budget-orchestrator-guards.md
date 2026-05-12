# Phase 2 full-budget orchestrator guards and corpus-consumption caveat

Use this note when E10 has moved beyond adapter-smoke into a resumable `main_100m` / full-budget Phase 2 orchestrator, but the run is still partial and formal `Y_recover` is not yet justified.

## Session-derived trigger

- A real `main_100m` resume chunk executed with `training_executed=true`, `checkpoint_written=true`, and `interval_eval_executed=true`.
- The run wrote or updated `phase2_orchestrator_plan.json`, `orchestrator_state.json`, job-table/checkpoint/eval artifacts, and `verification.json`.
- Token progress is far below the protocol budget (for example 2,304 / 100,000,000 per job), so only `Y_recover_partial` is valid.
- A corpus manifest proves provenance/capacity, but code inspection shows the trainer is still repeating quest-local split texts or another local surrogate instead of actually streaming from the manifest.

## Required guardrails

1. Re-read the formal command document, current-status entry, runner code, and config before launching another chunk. Do not rely on handoff prose.
2. Treat `phase2_streaming_corpus_manifest.json` as provenance/capacity only until the training loop is proven to consume it (or an explicitly equivalent audited stream) as the token source.
3. Do not scale a partial orchestrator to paper-scale `Y_recover` while the corpus-consumption path is only provenance-backed. First implement/validate manifest-backed streaming consumption and record that method fix.
4. In the runner, guard against silently reusing a run directory when the job grid or limits change. Persist enough plan metadata to detect changes in selected model/floorplan/rank/seed grid, protocol budget, and `--limit-*` settings.
5. Use append-only per-invocation records such as `orchestrator_chunk_recorcs.jsonl` for resume chunks so future agents can audit how cumulative tokens, evals, and checkpoints changed over time.
6. If manifest-backed streaming consumption is resumed across invocations, add a persisted per-family cursor (for example `phase2_corpus_cursor.json`) plus append-only corpus-consumption history; verify `cursor_before`/`cursor_after` from disk and make incompatible plan/grid/limit resumes fail before cursor or record side effects. See `references/phase2-streaming-cursor-resume.md`.
7. Keep completion gates per job, not aggregate. A total-token counter across jobs cannot satisfy a per-job 100M-token criterion.
8. Verify from disk after each chunk: latest verification, state, job table, checkpoint manifest/final adapter, interval eval JSONL, cursor/consumption artifacts when applicable, and absence of formal `recover_target_recorcs.jsonl` unless the per-job protocol budget is actually reached.
9. Pass `run-phase2-retrofit --out` as the command JSON file inside the run directory (for example `<run_dir>/run_phase2_retrofit.command.json`), not as the run directory itself. The runner derives `run_dir = out_path.parent`; a directory-valued `--out` can otherwise misplace side effects in the parent run root before failing. If this happens, quarantine the misplaced artifacts and do not count them.
10. Treat selector limit flags according to their CLI semantics: `--limit-models` expects comma-separated model IDs, not a numeric count. If the selector subset is already one model/job, omit `--limit-models`; if filtering is required, pass the actual model id such as `pythia-1b`. A numeric `--limit-models 1` can produce `ValueError: no Phase 2 adapter jobs selected` and should be recorded as a failed/no-side-effect invocation, not a formal run.
11. Update short-entry documentation (`experiments/CURRENT_STATUS.md`) and long source-of-truth docs only enough to preserve navigation and boundaries. Do not append bulky handoffs to already-long command/plan files.
11. For repeated homogeneous resume chunks under the same method boundary, prefer a rolling latest-status update plus one compact historical bullet/section per chunk. Avoid duplicating the full command transcript, full validation script, or long handoff in every document.
12. Record a main experiment when a real training/eval chunk runs, then milestone/decision artifacts that explicitly state `writes_y_recover=false` and `g2_satisfied=false` if still below budget or corpus-consumption is unresolved.

## Safe reporting language

Use:

- "real `main_100m` resume chunk verified checkpoint/eval/resume mechanics"
- "current output is `Y_recover_partial`, not formal `Y_recover`"
- "manifest proves corpus provenance/capacity; actual manifest-backed training consumption remains the next method gate"
- "G2 remains unsatisfied"

Avoid:

- "paper-scale evidence" when the trainer has not consumed the streaming corpus manifest
- "Phase 2 complete" before per-job budget completion and formal candidate-level records
- hiding job-grid/run-dir changes by resuming an old state silently
