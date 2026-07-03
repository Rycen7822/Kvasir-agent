# PF-REAL-009 Current State Notes

## Sources read

- `worknotes/real_cli_rounds/round1/delegations.json`
- `workers/ponder_cli_operator_observer.md`
- `delegation.py`
- `planner.py`
- `resources/skills/ponder-forge-usage/SKILL.md`
- `tests/test_prepare_delegations.py`
- `tests/test_cli_contract.py`

## Reproduced current payload facts

- `required_evidence_occurrences=2` in the first Round 1 child context.
- `has_json_skeleton=False`.
- `has_data_result_hint=False`.
- `has_critical_hint=False`.
- `has_role_specific_data_inspector=False`.

## Owner seams

- `delegation.py` owns native `delegate_task_payload` child context assembly.
- `planner.py` currently stores generic per-task context as a duplicated required-evidence line.
- `resources/skills/ponder-forge-usage/SKILL.md` is parent-facing guidance; useful to improve manual operation, but child reliability must be fixed in `delegation.py` because children receive delegation context.
- `tests/test_prepare_delegations.py` is the direct regression surface.

## Root cause hypothesis

The child contract is prose-only. The code exposes evidence type names but not the accepted schema shape or critical/gate expectations. `planner.py` and `delegation.py` both add the same required-evidence line.
