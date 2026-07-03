# Round 2 retry metric analyst report

- run_id: `pf_run_97ba23c5ffc5`
- task_id: `pf_task_aeeb9f2ec0a0`
- role: `metric_analyst`
- profile: `analysis`
- quest root analyzed read-only: `/home/xu/project/loop/DeepScientist/quests/001`
- report path: `/home/xu/project/autosci-delphi/ponder-forge/worknotes/round2_retry_metric_analyst_report.md`

## Critical finding

Stage10 is complete only as a conservative evidence package: large-eval and seed-robustness evidence passed, but model-family coverage and CE-selection gates failed; downstream and oral gates are closed; next work must close family/resource coverage and CE cost-to-contain weaknesses before downstream or oral-readiness claims.

## Sources read

Required sources:

- `/home/xu/project/loop/DeepScientist/quests/001/experiments/CURRENT_STATUS.md`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/12_paper_package/REPORT_AUDIT.json`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/08_meta/STAGE10_META_ANALYSIS.json`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/07_large_eval/LARGE_EVAL_SUMMARY.json`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/06_recovery/RECOVERY_TRAIN_EVAL_SUMMARY.json`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/12_paper_package/STAGE10_CLAIM_LEDGER.md`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/10_downstream/DOWNSTREAM_GATE_STATUS.json`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/12_paper_package/STAGE10_ORAL_READY_GATE.md`

Additional read-only context used to interpret the CE and family gates:

- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/08_meta/GATE_DECISION.md`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/08_meta/SELECTOR_METRICS.csv`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/00_freeze/STAGE10_STATE.json`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/scripts/stage10_meta_analysis.py`
- `/home/xu/project/loop/DeepScientist/quests/001/experiments/stage10/scripts/stage10_model_family_expansion.py`

No file under `/home/xu/project/loop/DeepScientist/quests/001` was modified.

## Actual gates and metrics

### Overall status

`CURRENT_STATUS.md:3-25` records `active stage: Stage10 / complete`, with `large_eval_gate_passed=true`, `seed_robustness_gate_passed=true`, `ce_selection_gate_passed=false`, `model_family_gate_met=false`, `downstream_gate_status=closed`, and `oral_ready_gate_status=closed`. It also states that no downstream run was executed and no downstream result manifest exists.

`REPORT_AUDIT.json:327-416` independently records `ce_selection_gate_passed=false`, `model_family_gate_met=false`, `downstream_gate_status=closed`, `downstream_run_executed=false`, `oral_ready_gate_status=closed`, `forbidden_claim_scan_passed=true`, and 29 artifact hashes.

### Large eval: passed, panel-scoped

`LARGE_EVAL_SUMMARY.json:3-58` reports:

- status: `passed_S10-12_large_heldout_eval_alignment_audit`
- evaluated endpoint rows: `360`
- expected formal endpoint rows: `360`
- total rows including original references: `366`
- hard failures: `[]`
- six active models, each with row_count `61`

Interpretation: the large heldout eval is real and complete for the frozen Stage10 active panel. It does not by itself open model-family, downstream, oral-ready, or pretrained-reference-superiority claims.

### Seed robustness: passed, bounded to recorded grid

`STAGE10_META_ANALYSIS.json:50-65` reports `seed_robustness_gate_passed=true`, with 126/126 completed rows at 30M and 126/126 completed rows at 100M. `RECOVERY_TRAIN_EVAL_SUMMARY.json:22-30` reports `seed_robustness_row_count=252`, `target_write_ledger_rows=1380`, and `target_write_ledger_matches_endpoint_rows=true`.

Interpretation: seed robustness passed for the recorded Stage10 seed grid and existing panel. If the panel, selector set, or recovery protocol changes, this evidence must be regenerated rather than reused as a blanket stability claim.

### CE selection: formal gate failed; cost-to-contain remains the immediate weakness

`STAGE10_META_ANALYSIS.json:2-15` and `GATE_DECISION.md:5-12` report:

- `ce_selection_gate_passed=false`
- `cfc_baseline_retained=true`
- closed reason: `CE selection gate did not beat CFC-only on both macro regret@3 and cost-to-contain`

The underlying selector table shows why the gate remains conservative. `SELECTOR_METRICS.csv:2-7` and `GATE_DECISION.md:16-23` give:

| selector | macro regret@3 | mean cost-to-contain winner | delta regret@3 vs CFC | delta cost vs CFC | beats CFC regret@3 | beats CFC cost | top3 containment |
|---|---:|---:|---:|---:|---|---|---:|
| OrbitRepair-Proxy | 0.0058068827370489386 | 4.833333333333333 | -0.0388905861737987 | -9.0 | true | true | 5/6 |
| LoopCert-only | 0.03223671717595801 | 16.666666666666668 | -0.012460751734889634 | +2.833333333333334 | true | false | 3/6 |
| family-balanced blend | 0.03223671717595801 | 16.666666666666668 | -0.012460751734889634 | +2.833333333333334 | true | false | 3/6 |
| risk-calibrated blend | 0.03223671717595801 | 16.666666666666668 | -0.012460751734889634 | +2.833333333333334 | true | false | 3/6 |
| Pareto-front | 0.03313607480648891 | 16.5 | -0.011561394104358733 | +2.666666666666666 | true | false | 3/6 |
| CFC-only | 0.044697468910847644 | 13.833333333333334 | 0.0 | 0.0 | false | false | 3/6 |

`stage10_meta_analysis.py` defines CE-gate success over the configured contender names `LoopCert-only`, `Pareto-front`, `risk-calibrated blend`, and `family-balanced blend` (`stage10_meta_analysis.py`, searched lines 410-424). Those contenders improve macro regret@3 but fail cost-to-contain versus CFC-only. OrbitRepair-Proxy is a strong pressure baseline, but it is not the configured Stage10 contender success condition and cannot be used to override the audited `ce_selection_gate_passed=false` state.

Interpretation: the next CE work should explicitly optimize or constrain cost-to-contain, preserve CFC-only as the retained baseline, and pass the exact predeclared gate rather than relying on a non-contender proxy row.

### Model-family gate: failed/resource-gated

`STAGE10_META_ANALYSIS.json:18-31` and `LARGE_EVAL_SUMMARY.json:8-19` report:

- active entry count: `6`
- active family count: `4`
- `model_family_gate_met=false`
- status: `resource_gated_family_gate_failed`
- resource-gated model ids: `gemma-2-2b`, `smollm2-1.7b`, `opt-1.3b`, `falcon-rw-1b`, `stablelm-2-1.6b`, `mistral-7b-score-side-stress`

`stage10_model_family_expansion.py:37-39` defines minimums of 6 active families, 8 active model entries, and 3.0B score-side stress scale; searched lines 199-234 show resource-gated entries are not counted as active evidence and must not be used for oral-ready family coverage.

Interpretation: Stage10 evidence is below the family/resource gate. The next work must activate enough model families/resources and rerun dependent evidence before claiming broader coverage.

### Downstream gate: closed, no downstream result

`DOWNSTREAM_GATE_STATUS.json:2-23` reports:

- `downstream_gate_status=closed`
- `downstream_run_executed=false`
- `result_manifest=null`
- closed reasons: CE selection did not beat CFC-only on both required metrics; model-family gate is resource-gated
- gate inputs: CE false, large eval true, seed robustness true

Interpretation: downstream utility was not evaluated. The closed status is an intentional safety gate, not a downstream result artifact.

### Oral gate: closed

`STAGE10_ORAL_READY_GATE.md:5-11` reports `Status: closed` and gives the same two reasons: CE selection did not beat CFC-only on both macro regret@3 and cost-to-contain, and the model-family gate is resource-gated. Its boundary explicitly says Stage10 may be analyzed as a conservative evidence package but does not carry venue-readiness, downstream utility, or pretrained-reference-superiority claims.

### Claim boundaries

`STAGE10_CLAIM_LEDGER.md:7-15` records:

- `model_family_gate`: failed; resource-gated coverage below oral gate
- `ce_selection_gate`: failed; CFC baseline retained and CE selection success is not claimed
- `large_eval_alignment`: passed only for frozen Stage10 panel
- `seed_robustness`: passed only for recorded Stage10 seed grid
- `downstream_utility`: not evaluated; no downstream result manifest under closed gate
- `oral_gate`: closed; no venue-readiness claim
- `original_reference_improvement`: not evaluated; recovered endpoints are not claimed to improve on pretrained reference
- `theory_package`: supported only as a bounded certificate proposition with counterexamples

`CURRENT_STATUS.md:38-40` repeats the forbidden claims: do not claim recovered recurrent models beat original pretrained models, downstream utility improves, oral readiness, universal recovery guarantees, rank1 always wins, or mechanism-term importance beyond ablation/patching evidence.

## Metric output evidence

Read-only command run from `/home/xu/project/autosci-delphi/ponder-forge`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
# Inline read-only Python parser over required Stage10 JSON/Markdown artifacts.
# It loads CURRENT_STATUS, REPORT_AUDIT, STAGE10_META_ANALYSIS, LARGE_EVAL_SUMMARY,
# RECOVERY_TRAIN_EVAL_SUMMARY, STAGE10_CLAIM_LEDGER, DOWNSTREAM_GATE_STATUS,
# and STAGE10_ORAL_READY_GATE, then prints a JSON gate/metric consistency summary.
PY
```

Exit code: `0`.

Key output values:

- `stage_status`: `Stage10 / complete`
- `audit_status`: `passed_S10-15b_paper_package_final_report_handoff`
- `large_eval.evaluated_endpoint_rows`: `360`
- `large_eval.expected_formal_endpoint_rows`: `360`
- `large_eval.total_table_rows_including_original`: `366`
- `large_eval.hard_failures`: `[]`
- `recovery.seed_robustness_row_count`: `252`
- `recovery.total_endpoint_count`: `1380`
- `recovery.target_write_ledger_matches_endpoint_rows`: `true`
- `meta_gates.large_eval_gate_passed`: `true`
- `meta_gates.seed_robustness_gate_passed`: `true`
- `meta_gates.ce_selection_gate_passed`: `false`
- `meta_gates.model_family_gate_met`: `false`
- `meta_gates.downstream_gate_status`: `closed`
- `meta_gates.oral_ready_gate_status`: `closed`
- `model_availability.active_entry_count`: `6`
- `model_availability.active_family_count`: `4`
- `model_availability.status`: `resource_gated_family_gate_failed`
- `downstream.run_executed`: `false`
- `downstream.result_manifest`: `null`
- `oral_status_closed_in_markdown`: `true`
- `claim_ledger_boundaries_present`: `true`

## Reproduction log evidence

- All required files existed and were parsed read-only.
- The command used only Python standard-library JSON/path/regex reads; it did not import quest modules, generate caches, or write under the quest root.
- Additional read-only inspection of `GATE_DECISION.md`, `SELECTOR_METRICS.csv`, `STAGE10_STATE.json`, `stage10_meta_analysis.py`, and `stage10_model_family_expansion.py` was used to interpret the CE and model-family gates.
- This report is the only file written for this child task.

## Sanity check evidence

The command checked and returned true for all of the following:

- large eval rows match expected: 360/360
- seed rows match meta summary: 126 + 126 = 252
- downstream closed status is consistent across downstream, meta, and audit artifacts
- oral closed status is consistent across oral markdown, meta, and audit artifacts
- CE gate failed status is consistent across meta and audit artifacts
- family gate failed status is consistent across meta, large-eval model availability, and audit artifacts

## Next-step improvement recommendations

1. Keep Stage10 claims conservative.
   - Allowed claims: frozen-panel large eval passed; seed robustness passed on the recorded grid; Stage10 package is a conservative evidence package; component/theory evidence is bounded/diagnostic.
   - Disallowed claims: downstream utility, oral readiness, recovered recurrent models beating original pretrained references, universal recovery guarantees, rank1 always wins, or mechanism-term importance beyond recorded ablation/patching evidence.

2. Close family/resource coverage before making broader or oral-ready claims.
   - Current active coverage is 4 families and 6 entries; gate minimums are 6 active families and 8 active entries, plus a score-side stress-ready scale requirement.
   - Promote or replace the resource-gated models with active, license-cleared, locally evaluable entries, then rerun family audit, panel/recovery/eval/meta, and claim ledger as needed.
   - Do not count resource-gated entries as evidence.

3. Repair CE selection around cost-to-contain.
   - The LoopCert-family contenders lower macro regret@3 but lose mean cost-to-contain versus CFC-only.
   - A passing next selector must beat CFC-only on both macro normalized regret@3 and mean cost-to-contain under the exact predeclared Stage10 gate.
   - Treat OrbitRepair-Proxy as a pressure baseline or diagnostic target unless the gate definition is intentionally revised before evaluation.

4. Preserve large-eval and seed evidence as current-panel evidence only.
   - The existing evidence passed, but panel/selector changes invalidate the scope; rerun affected recovery endpoints, seed robustness, large eval, and meta analysis after such changes.

5. Keep downstream closed until upstream gates open.
   - Downstream was not run and has no manifest. Only after CE, large eval, seed, and family coverage gates are in the intended open state should a real downstream run produce a result manifest.

6. Keep oral-ready closed until CE, family, and downstream evidence all exist.
   - Stage10 completion alone is not venue readiness. Oral readiness requires repaired upstream gates plus a claim ledger that continues to exclude unsupported downstream, pretrained-reference, and universal-recovery claims.
