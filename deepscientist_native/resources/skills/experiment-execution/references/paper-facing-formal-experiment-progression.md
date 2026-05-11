# Paper-facing formal experiment progression

Use this note when the user asks to take over or continue a DeepScientist formal experiment and defines success as completing all paper-facing main figures/tables with formal data.

## Source-of-truth precedence

1. Active `idea/` documents are the highest-precedence scientific/protocol source.
2. Formal command documents describe execution, but must be patched when they lag or conflict with `idea/`.
3. `AGENTS.md` / quickstart handoffs are operational aids; repair them when stale.
4. Conversation summaries are helpful context, not authority over current files.

If implementation, AGENTS, or command docs conflict with `idea/`, follow `idea/` and record the reconciliation in the command doc and AGENTS.

## Bounded progression rule

- Continue from the earliest missing formal prerequisite, not the most exciting later figure/table.
- Execute one bounded experiment identifier/step at a time when the user says “continue next experiment”.
- Do not jump to packaging or paper figure generation until the upstream formal data for that figure/table exists and validates.
- Never promote `planned_not_executed`, smoke, synthetic/provenance prompt, or template-only artifacts into formal paper-scale results.

## Real-runner backfill pattern

When a command is still a recorder/stub:

1. Read `idea/`, formal command docs, runner code, tests, configs, and the latest validation JSON from disk.
2. Identify the next real substrate required by the protocol.
3. Add or patch a small real runner with tests first; use deterministic fixtures where possible.
4. If real model forward needs corpus text, materialize bounded local corpus text before extraction. Prefer protocol-matched dataset families; if a dataset route fails because of tool/library constraints, record the exact fallback and do not rewrite provenance.
5. Run via `ds_bash_exec` with a stable runstamp and bounded limits.
6. Validate output artifacts from disk: JSON parses, counts are nonzero/expected, all referenced artifact paths exist, finite numeric fields are finite, and validation flags explicitly show `planned_not_executed=false` for real steps.
7. Record `ds_record_main_experiment` for formal main experiments and `ds_artifact_record(kind="milestone"|"decision"|"report")` for surrounding decisions/reports.

## Boundary examples

- Raw corpus text materialization is a prerequisite/substrate; it is not a model result.
- Real trajectory extraction may be a formal main experiment only if it performs real forward passes and validates hidden-state/trajectory artifacts.
- Chart fitting creates a chart substrate; bounded fitting over a small layer-pair set is not full G1/main-table evidence unless the protocol says it is sufficient.
- Candidate scoring is score-side only. It may produce GAAS/CFC/ETD/RR/RawRepeat/Middle-cycle score records, but must not write `Y_frozen` or `Y_recover` unless the target-selection/retrofit step explicitly owns that boundary.
- Phase 2 retrofit/checkpoint/adapters and recovery evidence require separate validated training/evaluation artifacts.

## Documentation synchronization

After every verified step, patch:

- `experiments/正式实验命令.md` with current timestamp, exact run directory, command, validation result, and what the step does *not* prove.
- `experiments/EXPERIMENT_EXECUTION_PLAN.md` with current phase status.
- quest `AGENTS.md`; if a dev/source copy exists, synchronize it and verify equality or note deliberate divergence.

Keep final replies compact but explicit: completion time, runstamp, executed scope, output paths, key validation fields, what remains incomplete, and the next bounded step.