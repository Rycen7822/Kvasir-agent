# PF-REAL-009 Design Audit

## Request normalization

Fix a real delegation ergonomics defect discovered in Round 1: child agents receive enough context to write prose but not enough to reliably return parent-submittable JSON reports that pass Ponder-Forge gates.

Mode: design-plus-implementation. Scope is Ponder-Forge only.

## Sources inspected

- `delegation.py`
- `planner.py`
- `report_ingest.py` behavior via tests
- `gates.py` behavior via tests
- `resources/skills/ponder-forge-usage/SKILL.md`
- `tests/test_prepare_delegations.py`
- `tests/test_cli_contract.py`
- `tests/test_mini_cases_static.py`
- `worknotes/real_cli_rounds/round1/delegations.json`
- `workers/ponder_cli_operator_observer.md`

## Baseline design inventory

| id | existing element | current contract | evidence | owner/seam | risk |
|---|---|---|---|---|---|
| B1 | `delegation.py` child context | Emits goal, constraints, generic report prose, profile evidence list, and task context | lines 21-59 | delegation output seam | context lacks schema/gate/role details |
| B2 | `planner.py` task context | Stores `Required evidence types: ...` in each task | lines 44-50 | planning seam | duplicates delegation evidence line |
| B3 | `report_ingest.py` accepted schema | Accepts exact fields plus aliases; top-level evidence requires ids/refs | tests/test_report_ingest.py | report ingestion seam | child report may not ingest or may require parent repair |
| B4 | `gates.py` analysis profile | Critical analysis assertions require profile groups and metric command | tests/gates | gate seam | child may submit pass-looking but gate-blocking report |
| B5 | bundled skill | Gives parent workflow but not child schema skeleton | SKILL.md lines 46-52 | user guidance | manual operators still need schema details |
| B6 | real Round 1 payload | No JSON skeleton, no data_result/critical hints, no role-specific duties, duplicate evidence line | delegations.json parser | installed runtime output | defect is real and reproducible |

## Proposed design ledger

| id | baseline refs | decision | intent | files/seams | proof |
|---|---|---|---|---|---|
| D1 | B1,B3 | Embed a compact child report contract and JSON skeleton in every delegation context | make child output directly submittable | `delegation.py` | tests assert schema fields appear |
| D2 | B1,B4 | Emit profile-specific material-claim gate guidance for analysis, including `data_result`, `critical`, `metric_output.command`, `exit_code`, and evidence groups | avoid hidden gate blockers | `delegation.py` | tests assert profile guidance |
| D3 | B1,B2,B6 | De-duplicate required evidence text by suppressing task context when it equals generated profile line | remove prompt noise without changing planner storage | `delegation.py` | test count is 1 |
| D4 | B1,B6 | Add role-specific duty lines for known profile roles | reduce duplicate child work and improve evidence coverage | `delegation.py` | tests check data_inspector/metric_analyst duties |
| D5 | B5 | Add a compact child report contract section to bundled skill | improve manual operation and docs consistency | SKILL.md | static test asserts CLI-first and no direct-tool wording still pass |

## Compression review

| id | baseline refs | decision refs | action | why not append-only | code pressure | proof |
|---|---|---|---|---|---|---|
| C1 | B1 | D1,D2,D4 | rewrite in owner seam | delegation output is the public child contract; no new tool/subcommand is needed | small helper strings | prepare-delegations tests |
| C2 | B2 | D3 | keep planner, filter duplicate at delegation | avoids changing stored task semantics or migrations | subtracts duplicate prompt line | count test |
| C3 | B5 | D5 | narrow doc patch | skill remains parent guide; child reliability comes from delegation context | small docs | static tests |

## Implementation gate

Authorized edits:

- `delegation.py`
- `resources/skills/ponder-forge-usage/SKILL.md`
- `tests/test_prepare_delegations.py`
- `tests/test_mini_cases_static.py` only if static expectations need extending
- worknotes only

No new CLI subcommand, no new storage schema, no new plugin tool surface.

## Proof and false-green risks

Required proof:

1. RED: existing `prepare_delegations` output lacks schema/data_result/critical/role hints and duplicates evidence text.
2. GREEN focused tests: `tests/test_prepare_delegations.py`.
3. Full source tests.
4. Source compileall.
5. Copy install smoke.
6. Installed-copy tests and compileall.
7. Fresh installed CLI real reproduction: start/plan/delegations for analysis task must show schema, data_result, critical, role guidance, and a single required-evidence line.

False-green risks:

- Tests check only generic profile and miss analysis specifics.
- Context becomes too verbose; keep skeleton compact.
- Skill gets direct-tool wording by accident; static test must still reject `ponder_forge_` guidance.
- Existing queued runs keep old context; revalidation must use a fresh installed run.

## Rollback

Revert `delegation.py` and skill/test patches, reinstall previous committed plugin, and continue Round 1 with parent-curated manual reports. The live quest path remains untouched.
