# Phase 2 adapter-smoke to full-budget E10 progression

Use this note when a CodexScientist quest has progressed from Phase 2 selector/corpus provenance and a planned retrofit recorder to a real but bounded recurrent-core adapter smoke run. It captures how to keep advancing E10 without overclaiming G2.

## Trigger pattern

- Formal command document names an E10/Phase 2 retrofit or recovery-training step.
- A streaming corpus provenance manifest exists or can be made active.
- The old `run-phase2-retrofit` path has been upgraded from `planned_not_executed` to a real adapter training/eval substrate.
- A smoke run has produced checkpoint/eval artifacts but consumed far below the protocol token budget, e.g. 128 tokenizer-counted tokens vs 100M.

## Execution discipline

1. Re-read the formal command document and active idea/protocol implementation documents before acting; do not rely on handoff summaries.
2. Keep the active boundary at E10 until protocol-budget Phase 2 training, interval eval, checkpointing, and candidate-level `Y_recover` are complete.
3. Treat adapter-smoke as a real training-path validation only, not as G2 evidence.
4. Validate artifacts from disk after the smoke run:
   - command JSON exists and parses;
   - `verification.json` reports `planned_not_executed=false`, `training_executed=true`, `checkpoint_written=true`, `interval_eval_executed=true`;
   - job table exists;
   - per-job checkpoint manifest and final adapter checkpoint exist;
   - interval eval JSONL exists and metrics are finite.
5. Keep `writes_y_recover=false` and `g2_satisfied=false` when the job has not reached the configured protocol token budget.
6. Name any smoke-only output `Y_recover_smoke` or equivalent; never call it formal `Y_recover`.
7. Record a milestone and decision after validation. If `cs_record_main_experiment` fails on optional chart rendering, use validated disk artifacts plus `cs_artifact_record` for durable routing rather than rerunning the experiment blindly.
8. Update `experiments/正式实验命令.md`, `EXPERIMENT_EXECUTION_PLAN.md`, and the active quest-local `AGENTS.md`. Only update a dev-copy `AGENTS.md` when the user has explicitly asked for cross-copy sync; a user instruction to focus on the current quest/project and not touch a dev-copy directory supersedes older sync habits.

## Next-step boundary after smoke

The next formal step should be a full-budget/resumable Phase 2 orchestrator, still under E10:

- tokenizer-counted streaming corpus consumption to the protocol budget;
- fixed selector / floorplan / rank / seed job grid;
- checkpoint resume and recovery after interruption;
- interval eval at configured token boundaries;
- candidate-level `Y_recover` only after each job reaches the full token budget;
- residual/statistics only after formal `Y_recover` is present.

When implementing or validating the full-budget orchestrator, make the completion gate per job, not aggregate across jobs. A bounded `main_100m` partial run may legitimately write `phase2_orchestrator_plan.json`, `orchestrator_state.json`, job-table/checkpoint/eval artifacts, and `verification.json` with `training_executed=true`; it still must report `writes_y_recover=false`, `recover_target_records_present=false`, and `g2_satisfied=false` unless every selected job individually reaches the protocol token budget and has finite checkpoint/eval evidence. Label partial eval outputs as `Y_recover_partial` rather than formal `Y_recover`.

Before scaling a partial orchestrator into formal `Y_recover`, verify that the training loop actually consumes the intended streaming corpus manifest or an explicitly equivalent audited stream. A manifest that proves provenance/capacity is not, by itself, evidence that training used that corpus; repeated quest-local split texts or other local surrogates are only a method substrate and must be reported as a gap. For detailed same-run-dir/job-grid guards and append-only resume chunk records, see `references/phase2-full-budget-orchestrator-guards.md`.

For partial/resume validation, check from disk that:

- `planned_not_executed=false` and `execution_mode=main_100m`;
- `phase2_orchestrator_plan.json` fixes the selected model/floorplan/rank/seed grid and protocol budget;
- `orchestrator_state.json` contains per-job cumulative token counters and remaining token budget;
- `min_job_cumulative_tokens` is reported separately from total tokens so aggregate progress cannot satisfy a per-job gate;
- per-job final or resumable checkpoints and interval eval JSONL exist and contain finite metrics;
- `recover_target_recorcs.jsonl` is absent until formal candidate-level recovery is justified.

Do not jump to E11/E12 or paper packaging after smoke-only or partial-orchestrator validation.

## Reporting language

Good wording:

- "adapter-smoke verified the real training/eval substrate"
- "training_executed=true, but tokenizer_counted_train_tokens is below protocol budget"
- "writes_y_recover=false; G2 remains unsatisfied"

Avoid:

- "Phase 2 complete"
- "G2 achieved"
- "Y_recover generated" when the output is smoke-only
- hiding token-budget shortfall behind successful checkpoint/eval artifacts
