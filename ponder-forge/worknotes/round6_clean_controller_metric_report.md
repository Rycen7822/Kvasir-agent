# round6_clean Controller Metric Report

- run_id: `pf_run_c0f170979d4d`
- quest_path: `/home/xu/project/loop/DeepScientist/quests/001`
- write boundary: quest path is read only; this report is under Ponder-Forge worknotes.

## Stage10 status

- large_eval_status: `passed_S10-12_large_heldout_eval_alignment_audit`
- evaluated_endpoint_rows: `360`
- token_weighted_rows_including_original: `366`
- split_record_count: `18789`
- active_family_count: `4`
- model_family_gate_met: `False`
- downstream_gate_status: `closed`
- downstream_run_executed: `False`
- closed_reasons: CE selection gate did not beat CFC-only on both macro regret@3 and cost-to-contain, Model-family gate is resource-gated

## Next-step recommendations

1. Keep Stage10 claim boundaries closed: no oral-ready, downstream-utility, or pretrained-reference-superiority claim while CE/model-family/downstream gates remain closed.
2. Reduce LoopCert/Pareto cost-to-contain while preserving regret@3 gains; CE selection failed because cost did not beat CFC-only.
3. Open model-family coverage by resolving resource-gated families or narrowing the claim population explicitly.
4. Run downstream only after CE and model-family gates open, then require a downstream result_manifest before any utility claim.
