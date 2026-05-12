# Phase 2 autonomous resume loop guardrails

Use this note when a CodexScientist Quest asks for autonomous, experiment-only continuation of a resumable Phase 2 `main_100m` run until formal `Y_recover` / gate satisfaction.

## When to use

- The user explicitly authorizes autonomous experiment execution, but excludes paper writing/packaging.
- The formal plan requires repeated compatible resume chunks under one run directory until a fixed token budget is reached.
- Single chunks are safe and verified, but many iterations are required.

## Durable execution rules

1. Keep the mode contract explicit in quest state: autonomous + experiment-execution-only + no paper writing/packaging.
2. Use CodexScientist-native execution for quest commands. Prefer `cs_bash_exec` for shell/Python/monitoring so bash sessions and logs are durable; avoid generic terminal/process background jobs for CodexScientist quest work unless no native background facility exists, and then immediately write a quest-local summary file and record the exception.
3. Use the quest's working environment, not bare `python`. For Quest001, the known-good interpreter was `/home/xu/project/loop/.venv/bin/python`; bare `python` could fail with missing packages such as `numpy`.
4. Reuse the same compatible run directory and command JSON path. Do not change model/floorplan/rank/seed grid, corpus manifest, source mode, cursor path, token budget semantics, or limit fields unless the plan explicitly permits a new run line.
5. Before each chunk, read the current `orchestrator_state.json` and `phase2_corpus_cursor.json`; after each chunk, validate both and append a concise JSONL event to a quest-local autonomous summary file.
6. Stop only when one of these is true: fixed budget reached and formal `Y_recover` is written; gate failure/runner failure occurs; plan says later steps should begin; or the user interrupts.

## Per-chunk summary event

Write one `before_chunk` and one `chunk_completed` JSON object per iteration. Include at least:

- `iteration`, `runstamp`, `chunk`, `current`, `remaining`
- `cursor_before_fineweb_edu`, `cursor_after_fineweb_edu`, and cursor-file value after the run
- `record_index_start`, `record_index_end`, `record_count`, `selected_text_count`
- `min_job_cumulative_tokens`, `protocol_token_budget`, `remaining_protocol_tokens`
- `returncode`, `all_checks_passed`, `verification_failures`
- `checkpoint_exists`, `eval_exists`, `train_log_exists`
- `recover_target_exists`, `writes_y_recover`, `g2_satisfied`

## Validation after each chunk

- `run_phase2_retrofit.command.json` parses and matches the compatible plan.
- `verification.json` reports all checks passing.
- `orchestrator_state.json` cumulative tokens increased by exactly the intended chunk unless the final chunk is smaller to hit the budget exactly.
- `phase2_corpus_cursor.json` advanced from the prior cursor and matches the latest consumption record.
- `phase2_corpus_consumption_recorcs.jsonl` gained one append-only record whose selected row range matches the chunk summary.
- Checkpoint, interval eval, and train log exist.
- Formal `recover_target_recorcs.jsonl` / `Y_recover` is not claimed until the fixed budget is actually reached.

## Final validation and reporting

When the autonomous loop stops, do not rely on the stop event alone:

1. Re-read `run_phase2_retrofit.command.json`, `verification.json`, `orchestrator_state.json`, `phase2_corpus_cursor.json`, `phase2_corpus_consumption.json`, current/history records, `recover_target_recorcs.jsonl`, checkpoint, eval log, train log, and the autonomous summary JSONL.
2. Verify `min_job_cumulative_tokens == protocol_token_budget`, `remaining_protocol_tokens == 0`, `writes_y_recover == true`, `recover_target_recorcs.jsonl` is present/non-empty, checkpoint/eval/train logs exist, and the final cursor/range match the last summary event.
3. If the runner-level `g2_satisfied` field remains `false` because G2 is post-hoc rather than encoded in the runner, record that caveat explicitly. Close G2 only through a separate traceability/analysis bundle that checks residual/score traceability, downstream CE recoverability, training stability, systems metrics, cursor provenance, and checkpoint/eval evidence. Never silently overwrite the runner source field or claim paper-level statistical generalization from a one-job post-hoc traceability check.
4. Record the final main experiment, then update the short status, long plan header, command catalog, root status/summary, milestone, decision, and knowledge card. Keep paper-writing/package steps out of scope when the user said no paper.

## Reporting while loop is still running

If the context is about to end or the user asks for status while the loop is still partial, report:

- the latest verified cumulative token count and cursor range;
- the loop summary path;
- whether `writes_y_recover` / `g2_satisfied` is still false;
- which todo remains active for final validation and durable recording.

Never convert an autonomous loop's partial progress into a completed-plan claim.