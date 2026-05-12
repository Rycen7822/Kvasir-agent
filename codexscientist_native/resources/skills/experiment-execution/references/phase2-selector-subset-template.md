# Phase 2 selector subset template notes

Use this reference when a CodexScientist experiment command document advances from Phase 1B stats into Phase 2 selector subset setup, but real Phase 1A frozen benchmark results do not yet exist.

## Quest001-derived pattern

In Quest001, E10 starts with `E10.1` selector subset template creation before retrofit planning/running:

- E10.1 creates `experiments/manifests/phase2_selector_subset.template.json` and a run-local copy.
- It must not create or treat `experiments/manifests/phase2_selector_subset.json` as complete unless real Phase 1A frozen benchmark results exist.
- E10.2 retrofit plan and E10.3 `run-phase2-retrofit` are separate later steps. Do not execute them when the user asked for only the next step after E09.
- Report the step as `completed_template_only`, not as Phase 2 execution.

Expected template shape:

```json
{
  "schema": "gaas_loop.phase2_selector_subset.v1",
  "status": "template_replace_before_real_run",
  "source_phase1a_run": "<absolute path to completed phase1a_frozen run directory>",
  "selection_rules": [
    "GAAS top-k",
    "GAAS+Coda top-k",
    "CFC top-k",
    "RawRepeat top-k",
    "ETD/RR canonical top-1/top-3",
    "matched random / stratified controls"
  ],
  "k": "<fill from phase2_retrofit.yaml or phase1a decision>",
  "selected_floorplans": [
    {
      "selector": "GAAS",
      "model_id": "<model_id>",
      "domain": "<domain>",
      "floorplan_ids": ["<floorplan-id-1>", "<floorplan-id-2>"]
    }
  ]
}
```

## Validation checklist

1. Verify both template files exist:
   - `experiments/manifests/phase2_selector_subset.template.json`
   - `experiments/runs/phase2_retrofit/phase2_subset_<RUNSTAMP>/phase2_selector_subset.template.json`
2. Parse JSON and confirm:
   - `schema == "gaas_loop.phase2_selector_subset.v1"`
   - `status == "template_replace_before_real_run"`
   - placeholders such as `<absolute path ...>` remain present.
3. Confirm `experiments/manifests/phase2_selector_subset.json` is absent unless a real Phase 1A result has been selected.
4. Write run summary JSON/MD with:
   - `formal_selector_subset_created: false`
   - `selector_subset_template_created: true`
   - `real_model_forward_started: false`
   - `real_training_started: false`
   - `real_phase2_retrofit_started: false`
   - `phase2_runner_invoked: false`
   - `stopped_after: E10.1 selector subset template`
5. In the milestone, state that E10.2/E10.3 were not executed.

## Pitfalls

- If a shell variable is assigned but not exported before a Python heredoc reads it via `os.environ`, the run can fail with `KeyError` (for example `OUT`). Either `export OUT=...` or pass variables through command arguments.
- Do not allow a failed pre-artifact attempt to pollute the final runstamp. Record the failed bash id in the successful run summary if useful, then validate the completed run from disk.
- `cs_artifact_record` requires `quest_id` as a top-level argument even if `payload.quest_id` is present.
