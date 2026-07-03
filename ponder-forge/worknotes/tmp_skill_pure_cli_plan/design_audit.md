# Ponder-Forge Skill + Pure CLI Design Audit

## 1. Request normalization

Desired outcome: convert Ponder-Forge from a Hermes plugin that exposes nine model-visible tools and six hooks into a workflow operated by a bundled skill and a pure Python CLI. The plugin may still provide a slash command and optional Hermes CLI subcommand, but default model-visible tool count must be zero.

Mode: design-plus-implementation.

Constraints: keep existing SQLite state and core graph/gate/finalize behavior; avoid over-design; no daemon/MCP/background service; no quest-path writes; update `note.md` after each meaningful slice; use small patches.

## 2. Sources inspected

- `plugin.yaml`
- `__init__.py`
- `schemas.py`
- `tools.py`
- `commands.py`
- `hooks.py`
- `resources/skills/ponder-forge-usage/SKILL.md`
- `config.py`
- `store.py`
- `planner.py`
- `delegation.py`
- `verifier.py`
- `gates.py`
- `renderer.py`
- `report_ingest.py`
- `tests/test_plugin_registration.py`
- `tests/test_tools_contract.py`
- `tests/test_prepare_delegations.py`
- `scripts/copy_install_smoke.py`
- Hermes docs: plugin registration supports tools, hooks, slash commands, CLI commands, and bundled skills; `ctx.register_tool` makes tools visible to the model.

## 3. Design iteration logs

### Iteration 1 — surface ownership

1. Question: which seam makes Ponder-Forge model-visible? Answer: `__init__.py` registers every `TOOL_NAMES` item from `schemas.py` via `ctx.register_tool`, and registers every `HOOK_NAMES` item via `ctx.register_hook`.
2. Question: is core behavior tied to Hermes tool registration? Answer: no; `tools.py` handlers are thin wrappers over ordinary modules and `store.py` uses SQLite under `HERMES_HOME`.

Research added: plugin manifest, registration code, tools, schema, hooks, store.
Design change: move public operation from `ctx.register_tool` to a stdlib CLI calling core modules directly.
Remaining uncertainty: CLI argument shape and tests.

### Iteration 2 — CLI and test contract

1. Question: how to submit structured reports without model-visible tools? Answer: CLI `submit-report --file <json>` uses `report_ingest.ingest_report`; `--file -` can read stdin for generated reports.
2. Question: how should Hermes users discover the workflow? Answer: bundled skill teaches CLI commands; slash command returns start output plus next CLI instructions; optional `register_cli_command` can expose `hermes ponder-forge ...` when runtime supports it.
3. Question: how to avoid append-only wrappers? Answer: implement `cli.py` as a thin dispatcher around existing functions, and rewrite plugin registration/tests instead of adding a bridge tool.

Research added: command and tests read; Hermes docs for `register_cli_command` and bundled skills.
Design change: choose true pure CLI, zero tool/hook registration, no one-tool bridge.
Remaining uncertainty: none blocking; exact `register_cli_command` test context can be implemented minimally.

## 4. Baseline design inventory

| id | existing element | current assumption/contract | evidence | owner/seam | risk if changed |
|---|---|---|---|---|---|
| B1 | Plugin manifest | Ponder-Forge provides 9 tools and 6 hooks | `plugin.yaml` | plugin public contract | Removing tools breaks tests and current in-session direct tool use |
| B2 | Plugin registration | `register(ctx)` exposes all tools/hooks plus slash command and skill | `__init__.py` | plugin registration seam | Wrong change can hide skill/command or leave tools visible |
| B3 | Tool handlers | Public workflow is implemented as JSON-returning tool handlers | `tools.py` | tool adapter seam | Deleting too early can lose tested workflow behavior |
| B4 | Core library | Store/planner/delegation/report/gate/verify/finalize are ordinary Python modules | `store.py`, `planner.py`, `delegation.py`, `report_ingest.py`, `gates.py`, `verifier.py`, `renderer.py` | core workflow seams | CLI must preserve behavior and state paths |
| B5 | Slash command | `/ponder-forge` only starts a run and tells model to call a tool | `commands.py` | command seam | Pure CLI would stall if slash command still references hidden tools |
| B6 | Bundled skill | Skill instructs direct use of nine tools | `resources/skills/.../SKILL.md` | operator guidance seam | Skill could reintroduce invalid workflow instructions |
| B7 | Hooks | Hooks track subagents and inject status/role policy | `hooks.py` | runtime hook seam | Removing hooks loses convenience tracking but not core graph behavior |
| B8 | Tests/install smoke | Tests assert old tool/hook counts and direct tool chain | `tests/test_plugin_registration.py`, `tests/test_tools_contract.py`, `scripts/copy_install_smoke.py` | verification seam | Tests must prove new contract without false green |
| B9 | Child/reviewer guidance | Delegation contexts and reviewer prompts tell child agents to call direct Ponder-Forge tools | `delegation.py`, `prompts/reviewers/*.md`, `tests/test_profile_verifiers.py` | child instruction seam | Hidden tool names would break pure CLI operation even after plugin registration is fixed |
| B10 | Hook/role policy tests | Hook tests and role policy exist only for the old registered hook surface | `hooks.py`, `role_policy.py`, `tests/test_hooks_reconcile.py` | obsolete hook seam | Leaving them after hook removal creates dead code and false contracts |

## 5. Proposed design ledger

| id | baseline refs | proposed decision | intent | files/seams touched | expected impact | rollback/proof |
|---|---|---|---|---|---|---|
| D1 | B4 | Add stdlib `cli.py` that calls existing core modules directly and emits JSON | Preserve workflow without model-visible tools | `cli.py`, tests | New pure CLI public surface | Roll back `cli.py`; proof via CLI RED/GREEN workflow test |
| D2 | B1,B2,B7 | Stop registering Ponder-Forge tools and hooks by default; manifest reflects no tool/hook surface | Remove context/tool-choice cost | `plugin.yaml`, `__init__.py`, `scripts/copy_install_smoke.py`, registration tests | tool_count=0, hook_count=0, command/skill remain | Roll back registration; proof via plugin registration and install smoke tests |
| D3 | B5 | Rewrite slash command to return CLI-first instruction and optionally start via CLI/core without referencing hidden tools | Prevent stale tool guidance | `commands.py`, tests | `/ponder-forge` remains useful without tools | Proof: slash command output contains CLI next steps and no `ponder_forge_plan` tool instruction |
| D4 | B6 | Rewrite bundled skill to pure CLI operator guide | Keep agent behavior aligned with new surface | skill file | Agents use terminal CLI and native `delegate_task` only | Proof: static test checks skill has CLI commands and no direct tool instructions |
| D5 | B8 | Replace direct tool-chain tests with CLI contract tests; keep core behavior coverage | Avoid preserving obsolete public API | tests | Source and installed suites prove new contract | Proof: full suite and installed suite pass |
| D6 | B3,B7 | Delete the obsolete tool/schema/hook adapter files once CLI tests cover the workflow | Avoid leaving dead code after public registration is removed | `tools.py`, `schemas.py`, `hooks.py`, tests | Removes dead public-adapter layer and prevents accidental re-registration | Roll back file deletions; proof via CLI workflow, registration, search, and full tests |
| D7 | B9,B10 | Rewrite child/reviewer guidance and tests to parent-submitted CLI reports; delete hook-only role policy | Complete the pure CLI contract beyond registration | `delegation.py`, `prompts/reviewers/*.md`, `tests/test_prepare_delegations.py`, `tests/test_profile_verifiers.py`, `tests/test_hooks_reconcile.py`, `role_policy.py`, `scripts/run_mini_benchmark.py`, `tests/test_verifier_independence.py` | Child agents produce JSON; parent submits through CLI/core; no hidden direct tool guidance remains | Proof via static prompt tests, delegation tests, mini benchmark, verifier tests, stale-reference scan |

## 6. Compression review

| id | baseline refs | decision refs | compression action | why this is not append-only | code-size pressure | proof or deferral owner |
|---|---|---|---|---|---|---|
| C1 | B1,B2 | D2 | rewrite/delete public surface | Changes owning registration seam instead of adding a tenth bridge tool | reduce context and runtime surface | plugin registration/install tests |
| C2 | B4 | D1 | split | Separates core workflow from Hermes model-visible tool adapter | small add, reuses core modules | CLI workflow tests |
| C3 | B5 | D3 | rewrite | Removes stale tool-followup instruction in the command owner | neutral | command tests |
| C4 | B6 | D4 | rewrite | Replaces direct-tool operator doc with CLI operator doc | neutral | static skill tests |
| C5 | B8 | D5 | replace | Tests the new public contract instead of locking in obsolete tool count | neutral | full suite |
| C6 | B3,B7 | D6 | delete | Once `cli.py` owns the public workflow, the tool/schema/hook adapter files become misleading dead code | reduce code and remove accidental re-registration path | CLI and registration tests plus repository search for stale imports |
| C7 | B9,B10 | D7 | rewrite/delete | Rewrites guidance at the source and deletes hook-only policy instead of preserving hidden direct-tool assumptions | reduce stale contracts | static prompt/delegation tests and stale-reference scan |

## 7. Implementation plan summary

1. Add focused CLI tests that fail because `cli.py` does not exist and plugin registration still exposes tools/hooks.
2. Implement minimal `cli.py` around existing modules.
3. Rewrite plugin registration and manifest to zero tools/hooks while keeping skill and command.
4. Rewrite slash command and bundled skill to CLI-first guidance.
5. Update install smoke and static tests.
6. Delete obsolete `tools.py`, `schemas.py`, and `hooks.py` after CLI/registration tests are in place.
7. Run source tests, copy install, installed tests, compileall, search for stale old-tool guidance, and a small installed CLI smoke.

## 8. Proof plan and false-green risks

Proof commands:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cli_contract.py -q`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_plugin_registration.py tests/test_mini_cases_static.py -q`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`
- `python3 -m compileall -q .`
- `python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge`
- installed-copy full tests and compileall.
- installed-copy CLI smoke from `/home/xu/.hermes/plugins/ponder_forge`.

False-green risks:

- Tests call source modules directly and miss installed path behavior. Mitigation: installed-copy tests and installed CLI smoke.
- Plugin still lists tools in manifest but tests only inspect register output. Mitigation: manifest and registration assertions both expect zero tools/hooks.
- Skill still tells agents to call old tools. Mitigation: static skill test rejects `ponder_forge_start`/`ponder_forge_plan` direct-tool instructions.
- CLI mutates wrong `HERMES_HOME`. Mitigation: tests monkeypatch temp `HERMES_HOME`; installed smoke uses default installed state only for controlled workflow.

## 9. Blast-radius and rollback plan

Blast radius: Ponder-Forge plugin source, bundled skill, tests, install smoke, and worknotes only. Existing `~/.hermes/ponder_forge` state schema is unchanged.

Rollback: revert the commit to restore 9 tools/6 hooks; no data migration is involved. If CLI tests fail late, keep source unchanged except `cli.py` and tests until fixed; do not partially install a broken CLI.

## 10. Open questions or deferrals

- Whether to support `hermes ponder-forge ...` through `ctx.register_cli_command` depends on runtime API shape. Implementation will register it only when the context exposes that method; pure `python cli.py ...` remains the authoritative path.

## 11. Confidence review

Final answer: complete after implementation and verification. The plan was written, reread, corrected for stale child/reviewer guidance, implemented with source and installed-copy tests, and verified through copy-install smoke. Remaining uncertainty is limited to future Hermes runtime restart/hot-load behavior, not the source or installed-copy implementation.
