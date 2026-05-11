# DeepScientist formal experiment command handoffs

Use this reference when a user asks for a step-by-step command document they will execute themselves after an experiment implementation or roadmap pass.

## Trigger

- User asks to write a command document under a quest `experiments/` directory.
- User wants all commands in execution order and comments explaining outputs and save locations.
- The task is documentation/handoff only; do not run the formal experiments unless explicitly asked.

## Recommended document shape

1. Header with quest root, experiments root, timestamp, and purpose.
2. "执行前必读" section:
   - Document is not evidence that commands have been run.
   - If commands are run by Hermes/DeepScientist, they must go through `ds_bash_exec`.
   - Resources are read-only; outputs live under `experiments/`.
   - Protocol split/candidate-set boundaries.
   - Any known CLI caveat, especially `planned_not_executed` stubs.
3. Global shell variable block:
   - `PROJECT`, `QUEST`, `EXP`, `PYTHONPATH`, `RUNSTAMP`.
   - `mkdir -p` for manifests, logs, trajectories, scores, runs, analysis, figures.
4. Phase-ordered commands:
   - E00 baseline/resource/environment gate.
   - E01 engineering smoke.
   - E02 split manifest.
   - E03 floorplan enumeration.
   - E04 trajectory extraction.
   - E05 chart fitting.
   - E06 scores.
   - E07 Phase 0 sanity.
   - E08 Phase 1A frozen benchmark.
   - E09 statistics/robustness.
   - E10 selector subset + retrofit.
   - E11 appendix experiments.
   - E12 paper-facing outputs.
5. After every command block:
   - "会产出" list with exact absolute or `$EXP` paths.
   - Gate/pass conditions.
   - Explicit distinction between current planned/dry-run outputs and real-run outputs if applicable.
6. Post-run validation command:
   - Check `run_manifest.json`, `metrics.json`, `metrics.md`, `claim_validation.md`, `runlog.summary.md`.
   - Export placeholders used inside Python heredocs, e.g. `export RUN_DIR=<RUN_DIR>`.
   - Check finite numeric metrics.
7. DeepScientist recording instructions:
   - Ask user to provide run id, run dir, phase, baseline/waiver, metrics paths, claim validation, conclusion, and next action.

## Verification before final reply

- Re-read or inspect the current CLI help for important commands. Do not document flags that are not supported by the current code.
- Check required phase tokens (E00-E12 or the project-specific equivalent) are present.
- Check key manifest/output paths are present.
- Check markdown code fences are balanced.
- Search for placeholder bugs such as unexported variables that are later read from `os.environ`.
- Record quest memory and a milestone saying this was a command document only and whether any real experiment was executed.

## Pitfalls from session 2026-05-03

- A plan may contain a command template with a flag that the implemented CLI does not support. In that session, the roadmap showed `--selector-subset` for Phase 2, but `run-phase2-retrofit --help` only supported `--quest-root`, `--config`, and `--out`; the command document handled selector subset as a separate JSON file instead of documenting an unsupported flag.
- Current experiment-shaped CLI commands can be intentional `planned_not_executed` recorders after a code-only implementation pass. The command handoff must warn the user that such outputs are command plans, not completed model evidence.
- If a validation heredoc reads `os.environ['RUN_DIR']`, use `export RUN_DIR=<RUN_DIR>`, not a shell-local assignment immediately before a separate command block.
