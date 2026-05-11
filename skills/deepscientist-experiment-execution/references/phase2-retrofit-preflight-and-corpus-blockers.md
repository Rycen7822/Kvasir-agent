# Phase 2 retrofit preflight and corpus-blocker notes

Use this reference when a DeepScientist formal experiment has moved past Phase 2 selector setup and the next boundary is a real retrofit runner, but the full paper-scale training/evaluation chain may still be unavailable.

## Quest001-derived pattern

A planned `run-phase2-retrofit` recorder was not acceptable as a formal G2 result. The safe improvement was to convert the command into a bounded real preflight/blocker runner before claiming any Phase 2 recovery result.

The real preflight should write auditable artifacts such as:

- resolved command/config JSON;
- metrics JSON with `planned_not_executed=false`;
- blocker report and claim validation markdown;
- run manifest / artifact manifest;
- explicit booleans for `training_executed`, `writes_y_recover`, and `g2_satisfied`.

If the runner discovers insufficient materialized corpus for the required token budget, report a formal blocker such as `blocked_preflight_insufficient_training_corpus` and stop. Do not reinterpret the preflight as successful training.

## Required preflight checks

Before starting or claiming Phase 2 retrofit training, verify from disk:

1. real Phase 1A frozen benchmark outputs exist and are not planned records;
2. Phase 1B stats / selector subset were generated from real Phase 1A/E09 outputs;
3. `experiments/manifests/phase2_selector_subset.json` exists and has concrete model/floorplan rows;
4. selected model ids and floorplan ids are concrete, not placeholders;
5. the training corpus is materialized or streamable with auditable provenance;
6. the available token count meets the configured budget, or the run records a blocker instead of training;
7. adapter checkpoint and candidate-level `Y_recover` are only reported after real training/evaluation writes them.

## Safe blocker semantics

A real preflight blocker is progress, but it is not a G2 pass. In blocker reports and milestones, keep these fields explicit:

- `planned_not_executed=false` for the preflight runner itself;
- `training_executed=false` when no training loop ran;
- `writes_y_recover=false` unless candidate-level recovery records exist;
- `g2_satisfied=false` until full recovery metrics exist;
- `stopped_before=E11/E12` or equivalent boundary text.

When the blocker is insufficient corpus, include both the configured token budget and the measured/materialized token count. This prevents later sessions from mistaking a code-path improvement for paper-scale evidence.

## Corpus streaming-provenance gate

When materialized local sample text is too small for a 100M-token Phase 2 budget but official dataset metadata/shards are available, split the unblock into a separate corpus provenance step before implementing training:

1. Add a fixed corpus mix to the retrofit config before any `Y_recover` outcome is observed (for example per-family token quotas summing exactly to the required budget).
2. Write a dedicated `prepare-phase2-corpus`/equivalent command that does not train, but emits `planned_not_executed=false`, `training_executed=false`, `writes_y_recover=false`, `g2_satisfied=false`.
3. Produce an active manifest such as `experiments/manifests/phase2_streaming_corpus_manifest.json` plus a run-local copy. Include per-family dataset id/config/split, token quota, metadata path, sample source shards, local sample text counts, and SHA256/byte counts for artifacts.
4. Validate from disk that all configured families are `streaming_ready`, quotas sum to the configured token budget, sample shards are real data/LFS shards rather than README/license files, and any bounded materialized texts are labeled as samples/provenance only.
5. Rerun the Phase 2 preflight after the active manifest exists. The status may advance from `blocked_preflight_insufficient_training_corpus` to `blocked_preflight_missing_retrofit_training_loop`; this is still not G2.
6. Update the formal command document, execution plan, and AGENTS/handoff with both the corpus run and the rerun preflight, including the exact remaining blocker.

Treat `streamable_token_budget=100000000` as a provenance readiness statement, not proof that tokenizer-counted training consumed 100M tokens. The later training/eval runner must still write checkpoint artifacts, interval eval, and candidate-level `Y_recover` before any G2 claim.

## Next-step guidance

To unblock without weakening standards:

1. Prefer auditable corpus materialization or streaming with manifest provenance over lowering the token target silently.
2. If a smoke-sized training loop is needed for engineering validation, label it as smoke/engineering only and keep G2 false.
3. Add tests for both passable preflight and corpus-blocker paths before wiring the CLI.
4. Run the command through `ds_bash_exec`, validate artifacts from disk, then record milestone/decision with `ds_artifact_record`.
5. Update the formal command document and AGENTS/handoff after validation so future agents resume at the exact remaining boundary.

## Pitfalls

- `planned_not_executed=false` on a preflight runner only proves the preflight executed; it does not prove training happened.
- Do not jump to E11/E12 while `Y_recover` and adapter checkpoints are absent.
- Do not call a corpus-size blocker a completed experiment; call it a verified blocker with a minimal unblock list.
- Keep idea/protocol documents above stale command prose when they define model/floorplan/Phase 2 constraints.
