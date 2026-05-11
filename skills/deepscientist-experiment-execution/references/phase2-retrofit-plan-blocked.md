# Phase 2 retrofit plan prerequisite-block notes

Use this reference when a DeepScientist experiment command document advances from a Phase 2 selector subset template into a per-model retrofit-plan step, but the real selector inputs do not yet exist.

## Quest001-derived pattern

In Quest001, E10.2 (`gaas_loop.cli retrofit --model-id ... --floorplan-ids ...`) was the next bounded step after E10.1. It was not safe to invoke because all concrete selection inputs were missing:

- no real Phase 1A frozen benchmark run outputs existed; only planned-command recorder files were present;
- Phase 1B statistics / robustness artifacts were absent;
- `experiments/manifests/phase2_selector_subset.json` was absent;
- only `experiments/manifests/phase2_selector_subset.template.json` existed;
- E10.2 required concrete `MODEL_ID` and comma-separated `FLOORPLAN_IDS` selected from real Phase 1A results.

The correct action was to perform and record an E10.2 prerequisite check, mark it blocked, and stop. Do not substitute placeholder values such as `<MODEL_ID>` or `<floorplan-id-1>` just to make the command run.

## Safe handling

1. Re-read the command document around E10.2 before acting.
2. Inspect current Phase 1A and Phase 1B outputs from disk:
   - `experiments/runs/phase1a_frozen/**/metrics.json`
   - `experiments/analysis/stats/phase1a_frozen_summary.*`
   - `experiments/analysis/tables/table_frozen_benchmark.csv`
   - `experiments/analysis/claim_validation/phase1a_claim_validation.md`
3. Check whether `experiments/manifests/phase2_selector_subset.json` exists.
4. If real outputs or selector inputs are missing, do not invoke `gaas_loop.cli retrofit`.
5. Write a blocked run summary JSON/MD under `experiments/logs/run_manifests/` and a run-local `BLOCKED.md` under `experiments/runs/phase2_retrofit/e10_phase2_retrofit_plan_blocked_<RUNSTAMP>/`.
6. Include fields such as:
   - `experiment_id: E10.2`
   - `status: blocked_missing_phase1a_selection`
   - `retrofit_plan_command_invoked: false`
   - `real_model_forward_started: false`
   - `real_training_started: false`
   - `real_phase2_retrofit_started: false`
   - `formal_selector_subset_exists: false`
   - `stopped_after: E10.2 prerequisite check`
7. Record a milestone after validation, explicitly stating E10.3/E11/E12 were not executed.

## Required inputs to unblock

- a completed real Phase 1A frozen benchmark run directory with metrics, claim validation, and candidate-level traceability;
- a concrete `MODEL_ID`;
- concrete comma-separated `FLOORPLAN_IDS` selected from real Phase 1A results;
- either a filled `experiments/manifests/phase2_selector_subset.json` or an explicit user-approved selector choice.

## User-authorized idea-doc selector override

If the user explicitly instructs the agent to decide from the quest's idea/protocol documents instead of waiting for real Phase 1A selector scores, it is acceptable to unblock E10.2 for planned-command execution only, provided the selected inputs are concrete and source-grounded:

1. Read the active idea/protocol docs and cite the exact basis for model and floorplan choice.
2. Prefer the first low-ambiguity Phase 2 model when the idea doc orders models and provides a model-matched calibration rationale (Quest001 example: `pythia-1b`).
3. Derive floorplan ids from the already generated `floorplan_manifest.jsonl`, not from placeholders. A conservative Quest001 policy was one centered `F_main` / `mode1_fixed_template` representative per allowed `q`, using the idea document's fixed-template and middle-cycle prior, with deterministic tie-breaking.
4. Write `experiments/manifests/phase2_selector_subset.json` with a status such as `idea_doc_guided_provisional_selector_user_authorized` and an explicit warning that it is not a GAAS/CFC/ETD/RR top-k result from real Phase 1A scores.
5. Run only E10.2 and validate `retrofit_100m_plan.json` as `planned_not_executed`; do not run E10.3/E11/E12 in the same step.
6. Update quickstart/formal command notes so future agents know the selector subset is provisional but concrete.

## Pitfalls

- The `retrofit` CLI can write a plan for any nonempty string list; that does not mean placeholder or guessed ids are scientifically valid.
- A selector subset template is not an executable selector subset.
- Blocking at a prerequisite check is progress when it prevents invalid experiment artifacts.
- If AGENTS/quickstart files still say E10.2 is merely pending or the active stage is stale, update both source and loop copies and verify they are identical.
