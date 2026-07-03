# PF-REAL-010..015 Scope Requirements

## Status

- planning_document_complete: no
- clean_streak: reset to 0 after wave2 parent reproductions
- current_phase: consolidated contract-consistency repair planning

## Confirmed parent reproductions

- `worknotes/real_cli_rounds/round1/parent_reproductions_after_wave2.json`
  - missing required CLI arg is non-JSON
  - reconcile unknown run returns success
  - status after final still asks for finalize
  - analysis gate passes `metric_output.exit_code=1`
  - coding delegation contract contains placeholder and analysis evidence examples
- `worknotes/real_cli_rounds/round1/parent_profile_gate_matrix_repro.json`
  - coding failing-test-only gate passes
  - math `proof_check` passes while unadvertised
  - math resolved/negative counterexample-search evidence blocks

## Constraints

- Do not modify `/home/xu/project/loop/DeepScientist/quests/001`.
- Patch only Ponder-Forge owner seams.
- Keep pure CLI + bundled skill design; do not add Hermes tools/hooks.
- Keep fixes small and contract-aligned; avoid adding new runtime surfaces unless a missing surface is the root cause.
- After fixes: source tests, compileall, reinstall, installed tests, installed temp-home smokes, then restart three-round clean streak.
