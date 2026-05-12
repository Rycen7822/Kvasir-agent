# Planned-command recorder execution notes

Use this reference when a CodexScientist experiment command document advances into runner sections whose current CLI implementation is still a `planned_not_executed` recorder.

## Quest001-derived session pattern

In Quest001, the formal experiment command document advanced through E04-E07 while the CLI runners were still recorders. The safe behavior was to execute exactly the next bounded section, validate the JSON command record, state clearly that no real scientific artifacts were produced, then stop.

Observed recorder commands:

- E04 `extract-trajectories`
  - Phase 0 config: `experiments/configs/phase0_sanity.yaml`
  - Phase 1A config: `experiments/configs/phase1a_frozen.yaml`
  - JSON records were written, stdout logs were zero bytes, and no hidden/logits/zarr trajectory artifacts were created.
- E05 `fit-charts`
  - Config: `experiments/configs/phase1a_frozen.yaml`
  - JSON record was written, stdout log was zero bytes, and no identity/procrustes/chart manifests were created.
- E06 `score-candidates`
  - Phase 0 config: `experiments/configs/phase0_sanity.yaml`
  - Phase 1A config: `experiments/configs/phase1a_frozen.yaml`
  - JSON records were written, stdout logs were zero bytes, and no `candidate_scores.jsonl`, finite score values, or score-side records were created.
  - GAAS, GAAS+Coda, CFC, ETD-score, RR-score, RawRepeat, and Middle-cycle remained experiment-internal comparator scores, not formal CodexScientist baselines.
- E07 `run-phase0`
  - Config: `experiments/configs/phase0_sanity.yaml`
  - JSON record was written, stdout log was zero bytes, and no `metrics.json`, `candidate_scores.jsonl`, `claim_validation.md`, or G0 sanity judgment was created.

For these planned recorders, tee-created stdout logs can exist with size 0. This is acceptable if the command exit code is zero and the JSON record validates.

## Formal runner boundary + real smoke gate pattern

When the user explicitly asks for "formal experiments" but the next formal runner command is still a recorder, do not either stop at prose-only refusal or pretend the runner succeeded. Use a two-layer boundary:

1. Execute the source-of-truth formal command exactly once for the next bounded section.
2. Validate the command JSON from disk. If it returns `planned_not_executed`, record a formal blocked run directory rather than advancing to later phases.
3. Create explicit blocked artifacts so future sessions cannot mistake the boundary for a scientific result:
   - `run_manifest.json` with `status: blocked_real_<phase>_runner_missing`
   - `metrics.json` with `training_tokens_completed: 0`, `g2_satisfied: false`, and boolean availability fields for missing outcomes
   - `metrics.md`, `claim_validation.md`, `runlog.summary.md`, `artifact_manifest.json`, and `RUN.md`
   - a run-manifest summary under `experiments/logs/run_manifests/`
4. Record the blocked formal command as a CodexScientist main experiment or milestone/report, but phrase the outcome as blocked/unavailable, not completed.
5. If hardware/resources are available and it is the minimum next implementation gate, run a separate tiny real smoke step that proves local model/tokenizer loading and one real forward pass. Keep it clearly separate from the formal 100M-token retrofit or evaluation run.
6. For the smoke step, log and validate at least: model path, token count, finite loss, logits shape, hidden-state count, device/CUDA telemetry, peak memory when available, and `g2_satisfied: false`.
7. Patch the quest quickstart/command document after both layers so future agents know that the formal runner is blocked but the real forward path is verified.

Quest001 example: E10.3 `run-phase2-retrofit` returned `planned_not_executed`, so the run was recorded as `blocked_real_phase2_runner_missing`; a separate E10.3a smoke loaded local `pythia-1b` and produced a real finite-loss forward pass, without applying floorplans, training adapters, producing `Y_recover`, or satisfying G2.

## Validation checklist

1. Read the current command document section before acting; infer the next step from the last completed run summary, not memory alone.
2. Execute exactly the next bounded section and stop there unless the user explicitly asks for a wider range.
3. Validate JSON artifacts from disk:
   - file exists and is non-empty
   - JSON parses
   - `schema == "gaas_loop.planned_command.v1"`
   - `command` matches the section (`extract-trajectories`, `fit-charts`, `score-candidates`, `run-phase0`, etc.)
   - `status == "planned_not_executed"`
   - config path matches the command document
4. Treat empty stdout logs as acceptable only for planned-command recorders; do not generalize this to real runners.
5. For multi-part steps, validate every command record before recording a milestone:
   - E04: both Phase 0 and Phase 1A trajectory command records
   - E06: both Phase 0 and Phase 1A scoring command records
6. Write a run summary JSON/MD under `experiments/logs/run_manifests/` with:
   - runstamp
   - exact scope
   - baseline gate state
   - whether real model forward/eval/training started
   - whether real artifacts were created
   - output paths and artifact statuses
   - explicit `stopped_after`
7. Record a CodexScientist milestone after validation, stating explicitly that no real model computation or downstream artifacts were produced when the status is `planned_not_executed`.
8. Inspect quest state and, when useful, git status after the milestone so the final report includes current `baseline_gate`, pending decisions/messages, and HEAD.

## Reporting wording

- Say "completed as planned-command recorder" rather than implying the scientific experiment result exists.
- List missing real artifacts as expected current-code limitations, not as failures, when the command JSON status is `planned_not_executed`.
- Include the completion time, runstamp, exact stopped-after step, output paths, baseline-gate status, and whether real model forward/eval/training occurred.
- For E06 and later, continue to describe CFC/ETD/RR/RawRepeat/Middle-cycle as experiment-internal comparators unless a formal external baseline artifact is introduced later.
