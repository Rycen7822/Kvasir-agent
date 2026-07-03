# Ponder-Forge Real-Run Stability Note

## Current status

- started_at: 2026-07-04T03:51:33+08:00
- completion: not complete
- confidence: not 100%; real-run loop has just started.
- source_dir: `/home/xu/project/autosci-delphi/ponder-forge`
- installed_dir: `/home/xu/.hermes/plugins/ponder_forge`
- real_task_path: `/home/xu/project/loop/DeepScientist/quests/001`
- hard guardrail: do not modify any code or document under the real task path.

## Real task

Deeply understand `/home/xu/project/loop/DeepScientist/quests/001`, analyze STAGE10 results, and provide next-step improvement recommendations. This is a read-only analysis task.

## Loop rules reminder

- Use Ponder-Forge real workflow: start -> plan -> prepare delegations -> child reports -> independent verifier -> gate/finalize.
- Record plugin problems immediately to `worknotes/problems.md`.
- If plugin defects appear, write a focused repair plan under `worknotes/`, patch only Ponder-Forge, reinstall, and rerun real workflow.
- Do not treat unit tests alone as proof of long-run stability.
- At least two real-run rounds are required; stop only after two consecutive rounds with no new plugin defects.

## Installation baseline

- `hermes plugins list` shows `ponder-forge` enabled.
- `python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge` succeeded with 9 tools, 6 hooks, 1 command, 1 skill.
- Installed tree is a copied directory, not a symlink, and excludes `tmp/`, `reference/`, and nested `ponder_forge/`.

## Round log

### Round 1

- status: blocked before child delegation
- goal: exercise the full Ponder-Forge workflow on the STAGE10 read-only analysis task.
- current reminder: the quest path is OS-writable but must remain read-only for this task.
- real plugin defect PF-REAL-001: native `ponder_forge_start` failed with `TypeError: ponder_forge_start() got an unexpected keyword argument 'task_id'`.
- root-cause direction: Hermes runtime passes dispatch metadata kwargs to plugin handlers; Ponder-Forge registered raw one-argument handlers.
- repair plan: `worknotes/pf_real_001_repair_plan.md`; scratch: `worknotes/pf_real_001_scratch.md`; plan complete and 100% confidence for this narrow fix.
- fix applied: `__init__.py` now wraps registered tool handlers with a Hermes kwargs adapter; `tests/test_plugin_registration.py` now covers `task_id`/`tool_call_id` kwargs.
- verification: focused tests `7 passed`; full tests `36 passed`; copy install smoke succeeded.
- fresh installed plugin probe: 9 tools, 6 hooks, 1 command, 1 skill, and metadata kwargs accepted.
- boundary: this already-running TUI session still has stale pre-fix direct tool handlers. Continue Round 1 through a fresh installed plugin process for run/payload generation, then native `delegate_task` for real child work.
- second real plugin defect PF-REAL-002: generated child delegation payload did not include the real user goal, quest path, or read-only constraints; child agents would only receive generic role instructions. This is a severe blocker for faithful real-task execution and must be fixed before delegation.
- repair plan: `worknotes/pf_real_002_repair_plan.md`; scratch: `worknotes/pf_real_002_scratch.md`; plan complete and 100% confidence for this narrow fix.
- fix applied: `delegation.py` now includes the run goal and constraints in child contexts; `tests/test_prepare_delegations.py` covers the regression.
- verification: focused delegation tests `2 passed`; full tests `36 passed`; copy install smoke succeeded.
- regenerated installed payload: `worknotes/round1_retry_ponder_forge_payload.json`; run `pf_run_5886197fa2aa`; goal and READ ONLY constraints present in all 3 child contexts.
- next step: dispatch native `delegate_task` children using the corrected payload and require each child to write a worknotes evidence file outside the read-only quest path.
- native delegation dispatched: 3 child roles (`data_inspector`, `metric_analyst`, `reproduction_runner`) under delegation `deleg_7de2613e`; their reports are pending and must not be treated as complete until returned.
- harness boundary found after context continuation: the hand-written background delegation used stale task ids from the first payload attempt, while the corrected generated payload for run `pf_run_5886197fa2aa` has task ids `pf_task_522e1ac95919`, `pf_task_6bdddf4df693`, and `pf_task_b9fd736c3c1a`. This is not classified as a Ponder-Forge source defect, but those pending child reports must be treated as advisory unless their submitted task ids match the current run. The controller path now uses the corrected generated task id `pf_task_6bdddf4df693` for the metric report.

### Controller read-only baseline while children run

- `AGENTS.md` and `experiments/CURRENT_STATUS.md` say Stage10 is complete but explicitly bounded: S10-10 model-family gate failed/resource-gated, downstream and oral gates are closed, and no forbidden claims should be made.
- `experiments/report_archive/STAGE10_RESULTS_REPORT.md` records 29 hashed artifacts, recovery endpoint rows `1380`, seed robustness rows `252`, large-eval endpoint rows `360`, token-weighted eval rows `366`, selector count `6`, component ablation rows `11`, causal patching rows `96`, and theory stress tests `7`.
- `REPORT_AUDIT.json` passed final report audit markers and forbidden-claim scan, but records `model_family_gate_met=false` and `ce_selection_gate_passed=false`.
- `GATE_DECISION.md` shows OrbitRepair-Proxy still beats CFC on both regret/cost in this selector summary, while LoopCert-only and blends beat CFC regret but not cost; CE selection gate remains failed because the required combined beating criterion is not met.
- `STAGE10_CLAIM_LEDGER.md` keeps downstream utility, oral readiness, original-reference improvement, universal recovery, and mechanism success out of the allowed claim set.

### Round 1 finalize and late-report repair

- controller report submitted: `worknotes/round1_controller_metric_report.md`; report `pf_report_fd998f3b813f`; assertion `pf_assertion_6165393cb163`; evidence items `7`; artifacts `2`.
- independent verifier: fresh Hermes reviewer wrote `worknotes/round1_independent_reviewer_verdict.md` and accepted with confidence `0.96`; Ponder-Forge verdict `pf_verdict_f471ef68be7d` recorded as independent from `pf_task_6bdddf4df693`.
- Round 1 initially passed gate and finalized to `/home/xu/.hermes/ponder_forge/runs/pf_run_5886197fa2aa/final.md`.
- PF-REAL-003 found from the real final: final Markdown had only one assertion bullet and no evidence/artifact/verdict trace. Fix plan `worknotes/pf_real_003_repair_plan.md`; source and installed-copy tests are green after renderer trace fix.
- PF-REAL-004 found after context continuation: late background child reports submitted after finalization and changed the completed run's gate back to blocked. Fix plan `worknotes/pf_real_004_repair_plan.md`; source and installed-copy tests are green after completed-run report rejection and finalize idempotency fix.
- Round 1 conclusion: real workflow reached final but exposed 4 plugin defects/boundaries. Do not count it as a clean stability round.
- Next step: Round 2 fresh installed run using the corrected installed plugin; prove start/plan/prepare/report/independent-verify/gate/finalize, trace-rich final output, and completed-run immutability.

### Round 2 first attempt

- fresh run created: `pf_run_96b29420ba9a`; corrected prepare payload contained real goal and read-only constraints.
- fresh Hermes child `metric_analyst` wrote `worknotes/round2_metric_analyst_report.md` and submitted report `pf_report_2d5f07e8d4ce`, assertion `pf_assertion_ecfdb026e84c`.
- PF-REAL-005 found: analysis gate blocked because the child submitted `metric_output`, `transform_script`, and `sanity_check`, but the hidden analysis-specific rule requires `metric_output.command`; the child context did not expose that field requirement.
- fix plan: `worknotes/pf_real_005_repair_plan.md`; source and installed-copy tests are green after delegation guidance and gate diagnostic fix.
- Round 2 first attempt does not count as clean. Restart Round 2 from a fresh run with installed PF-REAL-005 fix.

### Round 2 retry clean pass

- fresh retry run: `pf_run_97ba23c5ffc5`.
- prepare payload proved PF-REAL-002/PF-REAL-005 fixes together: contexts contained the quest path, READ ONLY constraint, and analysis `metric_output.command` guidance.
- fresh Hermes child `metric_analyst` wrote `worknotes/round2_retry_metric_analyst_report.md` and submitted report `pf_report_17fe77db3633`, assertion `pf_assertion_b5bc1a78db53`.
- `ponder_forge_verify` created reviewer task `pf_task_2f02a035bc43`; fresh Hermes reviewer wrote `worknotes/round2_retry_independent_reviewer_verdict.md`, submitted report `pf_report_4d397a5320ef`, and recorded accepted verdict `pf_verdict_e5bce5aebfd5`.
- installed-copy gate/finalize check: `gate_before=passed`; final report contains Evidence trace, Artifact trace, Verifier verdicts, `metric_output`, `round2_retry_metric_analyst_report.md`, and `repro_reviewer`.
- completed-run immutability check: late report submission returned `success=false` with `run is already completed; report submission is closed`; gate stayed `passed`; final report sha256 stayed unchanged.
- result: clean stability pass #1 after PF-REAL-005.

### Round 3 clean pass

- fresh run: `pf_run_6fa8a73606e2`.
- run mode: fresh installed Ponder-Forge public toolchain with controller-side `metric_analyst` and `repro_reviewer` reports against the same read-only quest.
- start/plan/prepare passed; delegation context contained READ ONLY constraints and analysis `metric_output.command` guidance.
- metric report: `worknotes/round3_controller_metric_report.md`, report `pf_report_772cd12b9ab2`, assertion `pf_assertion_4d6879730a27`.
- reviewer report: `worknotes/round3_controller_reviewer_verdict.md`, report `pf_report_65188ad5ed7b`, verdict `pf_verdict_0b0b44aae75e`.
- installed-copy gate/finalize check: `gate=passed`, `final_status=final`; final report contains Evidence trace, Artifact trace, Verifier verdicts, `metric_output`, `round3_controller_metric_report.md`, and `repro_reviewer`.
- completed-run immutability check: late report submission returned `success=false` with `run is already completed; report submission is closed`; final report sha256 stayed unchanged.
- result: clean stability pass #2 after PF-REAL-005. Exit condition met: two consecutive fresh real-run passes with no new plugin issue.

### Verification closeout before commit

- source tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q` -> `38 passed`.
- installed-copy tests: same command under `/home/xu/.hermes/plugins/ponder_forge` -> `38 passed`.
- compileall passed for source and installed copy.
- quest path check: `git -C /home/xu/project/loop/DeepScientist status --short -- quests/001` returned no changes.

### Round 4 first attempt / PF-REAL-006

- guardrail refreshed from `worknotes/goal(禁止修改).md`; stricter stop rule is at least three real workflow rounds and three consecutive clean passes.
- fresh run created via current tool surface: `pf_run_496b1615dbc7`; plan/prepare produced three analysis roles and delegation context included quest path, READ ONLY constraints, and `metric_output.command` gate detail.
- native `delegate_task` launched for data_inspector, metric_analyst, reproduction_runner as `deleg_2383de9a`; result is still pending and cannot be used for final closeout until returned.
- controller-side real Stage10 read-only report wrote `worknotes/round4_controller_metric_report.md` and `worknotes/round4_controller_metric_summary.json`.
- PF-REAL-006 found: public `ponder_forge_report_submit` accepted alias-shaped report payload with `success=true` but returned `evidence_ids=[]`; gate then produced misleading `missing_critical_assertion` because alias keys were silently ignored.
- fix plan completed: `worknotes/pf_real_006_repair_plan.md`; source fix in `report_ingest.py` adds narrow alias normalization and fail-loud validation before mutation.
- RED reproduced: three new report-ingest tests failed on current code; GREEN after fix: `tests/test_report_ingest.py` -> `4 passed`; focused public/gate tests -> `12 passed`; full source tests -> `41 passed`; source compileall passed.
- install verification after fix: copy-install smoke installed 9 tools / 6 hooks / 1 command / 1 skill at `/home/xu/.hermes/plugins/ponder_forge`; installed-copy full tests -> `41 passed`; installed-copy compileall passed.
- fresh installed process alias smoke passed: alias payload created 2 evidence ids and malformed unlinked evidence failed with `unlinked evidence`; current TUI tool binding remains stale for `report_submit`, so clean reruns after PF-REAL-006 must use a fresh installed process or fresh Hermes process.
- Round 4 first attempt does not count as clean. Clean counter resets after PF-REAL-006; next step is fresh installed real workflow runs until three consecutive clean passes.

### Async delegation results for Round 4 first attempt

- `deleg_2383de9a` returned all three real child roles. The children performed read-only Stage10 analysis and wrote only Ponder-Forge worknotes/plots.
- Verified Ponder-Forge pool for `pf_run_496b1615dbc7`: 3 tasks, 7 reports, 29 assertions, 6 evidence items, 14 artifacts. Gate remains blocked.
- Root cause of the blocked state is PF-REAL-006 impact: reports submitted before the alias-normalization fix created unsupported critical assertions with dropped evidence. `reconcile` returned no safe repair and cannot infer missing evidence.
- This run proves native child delegation/report collection executed on the real Stage10 task, but it is a deliberately non-clean run and is not part of the post-fix clean streak.
- Subagents independently confirmed Stage10 conclusion: large eval and seed robustness pass; CE selection/model-family/downstream/oral gates remain closed; next work should prioritize cost-to-contain selector improvement, model-family resource coverage, stale hash/audit drift, taxonomy clarification, and downstream only after gates reopen.

### PF-REAL-007

- Full source tests exposed a fixture hygiene issue after cleanup: `tests/test_mini_cases_static.py` depended on ignored `worknotes/ponder_forge_smoke_report_template.md`.
- Repair plan completed: `worknotes/pf_real_007_repair_plan.md`.
- Fix: tracked fixture added at `tests/fixtures/ponder_forge_smoke_report_template.md`, test updated, ignored worknotes copy removed.
- Focused verification: `tests/test_mini_cases_static.py` -> `3 passed`.

### PF-REAL-008 and final clean streak

- Real trigger: after a fresh installed clean run passed, `gate_status` still returned placeholder metrics (`independent_review_coverage=0.0`, `artifact_reproducibility_coverage=0.0`, `final_statement_trace_coverage=0.0`) and `unsupported_critical_assertions` counted gaps instead of assertions.
- Repair plan completed: `worknotes/pf_real_008_repair_plan.md`.
- Fix: `gates.py` now computes supported critical assertion count, true unsupported assertion count, `blocking_gap_count`, independent review coverage, artifact-backed coverage, and final trace coverage from the graph.
- RED tests failed on the old implementation; GREEN after fix: `tests/test_gates_profiles.py` -> `7 passed`; full source suite -> `43 passed`; source compileall passed.
- Installed copy refreshed at `/home/xu/.hermes/plugins/ponder_forge`; installed-copy suite -> `43 passed`; installed-copy compileall passed; copy smoke reported 9 tools / 6 hooks / 1 command / 1 skill.
- Post-PF-REAL-008 clean pass #1: `round4_retry_clean` / `pf_run_1f1b9c2ef2b7`, alias payload, `gate=passed`, `final_status=final`, late report rejected, coverage metrics all `1.0`.
- Post-PF-REAL-008 clean pass #2: `round5_clean` / `pf_run_29228431433a`, canonical payload, `gate=passed`, `final_status=final`, late report rejected, coverage metrics all `1.0`.
- Post-PF-REAL-008 clean pass #3: `round6_clean` / `pf_run_c0f170979d4d`, alias payload, `gate=passed`, `final_status=final`, late report rejected, coverage metrics all `1.0`.
- The clean-run script compared nine Stage10 key files before/after by size, mtime, and sha256; `quest_key_files_unchanged=true`.
- Current stability judgement: PF-REAL-001..008 are closed in source and installed copy. Three consecutive post-last-fix real workflow rounds produced no new plugin defects.

## Skill + pure CLI conversion

### Planning start

- started_at: 2026-07-04T06:11:31+08:00
- completion: not complete; planning scratch and design audit have been created, implementation has not started.
- user request: convert Ponder-Forge into a true `skill + pure CLI` workflow and then execute the plan; avoid model-visible Ponder-Forge tools/hooks by default.
- scratch_dir: `worknotes/tmp_skill_pure_cli_plan/`
- design_artifact: `worknotes/tmp_skill_pure_cli_plan/design_audit.md`
- final_plan_target: `worknotes/2026-07-04-skill-pure-cli-implementation-plan.md`
- design rows: B1-B8 baseline, D1-D6 decisions, C1-C6 compression actions.
- key decision: add a stdlib CLI around existing core modules; rewrite plugin registration so default installed Ponder-Forge exposes zero model-visible tools and zero hooks; keep bundled skill and CLI/slash guidance.
- deletion decision: physical deletion of `tools.py`, `schemas.py`, and `hooks.py` is now in scope after CLI/registration tests cover the workflow, because keeping them would leave misleading dead adapters.
- confidence check: high confidence in design direction, but not yet 100% until final implementation plan is written, reread, and structurally checked.

### Plan complete

- plan_path: `worknotes/2026-07-04-skill-pure-cli-implementation-plan.md`
- plan_status: complete and structurally checked.
- structural checks: 9 tasks, balanced Markdown fences, design audit path present, explicit zero-tool/zero-hook target, deletion of `tools.py`/`schemas.py`/`hooks.py`, installed-copy verification, and no-commit policy all present.
- design audit correction: initial deferral of adapter deletion was rejected because it would leave dead code; final D6/C6 delete the obsolete tool/schema/hook adapters after CLI tests cover the workflow.
- confidence check: I am 100% confident the written plan is executable and aligned with the user request. Implementation has not started yet.

### Task 1 RED tests

- files changed: `tests/test_cli_contract.py`, `tests/test_plugin_registration.py`, `tests/test_copy_install_smoke.py`.
- RED command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cli_contract.py tests/test_plugin_registration.py tests/test_copy_install_smoke.py -q`.
- RED result: 6 failed as expected.
- failure coverage: missing `cli.py`; manifest still lists 9 tools; plugin register still exposes 9 tools/6 hooks; slash command lacks `next_command` and still relies on old tool path; copy-install smoke still reports `tool_count=9`.
- confidence check: 100% confident RED proves the replacement contract and is not a false failure.

### Task 2 CLI implementation

- file added: `cli.py`.
- focused command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cli_contract.py -q`.
- result: `2 passed`.
- code review: `cli.py` has no imports from `tools.py`, `schemas.py`, or `hooks.py`; it calls existing owner seams (`plan_run`, `prepare_delegations`, `ingest_report`, `verify_run`, `evaluate_gate`, `render_final_report`, `reconcile_run`) instead of duplicating core algorithms.
- redundancy check: no extra daemon, bridge tool, package framework, or workflow abstraction was added. The CLI is 275 lines and stdlib-only.
- confidence check: 100% confident Task 2 preserves workflow behavior through pure CLI for the tested path.

### Tasks 3-4 command and registration rewrite

- files changed: `commands.py`, `__init__.py`, `plugin.yaml`.
- focused command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_plugin_registration.py tests/test_copy_install_smoke.py -q`.
- result: `4 passed`.
- combined command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cli_contract.py tests/test_plugin_registration.py tests/test_copy_install_smoke.py -q`.
- result: `6 passed`.
- code review: `__init__.py` registers only `/ponder-forge` command and bundled skill; `plugin.yaml` has `provides_tools: []` and `provides_hooks: []`; `commands.py` returns installed-path CLI guidance and contains no old tool instruction.
- redundancy check: no bridge tool, no runtime hook, no compatibility toggle added.
- confidence check: 100% confident default plugin registration is now skill/command-only at source level.

### Task 5 bundled skill rewrite

- files changed: `resources/skills/ponder-forge-usage/SKILL.md`, `tests/test_mini_cases_static.py`.
- focused command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_mini_cases_static.py -q`.
- result: `4 passed`.
- skill review: skill now instructs installed-path `cli.py`, `start`, `plan`, `delegations`, native `delegate_task`, `submit-report --file`, `verify`, `gate`, `finalize`, `status`, and `reconcile`.
- stale guidance check: skill contains zero occurrences of `ponder_forge_start`, `ponder_forge_plan`, and `ponder_forge_report_submit`.
- confidence check: 100% confident bundled skill is pure CLI-first and no longer directs agents toward hidden Ponder-Forge tools.

### Task 6 scope correction

- pre-delete search found additional stale direct-tool contract surfaces: `delegation.py`, `prompts/reviewers/*.md`, `scripts/run_mini_benchmark.py`, `tests/test_prepare_delegations.py`, `tests/test_profile_verifiers.py`, `tests/test_verifier_independence.py`, `tests/test_hooks_reconcile.py`, and hook-only `role_policy.py`.
- design audit updated with B9/B10, D7, and C7.
- implementation plan Task 6 updated to rewrite child/reviewer guidance, mini benchmark, and tests before deleting obsolete adapter files.
- confidence check: 100% confident this correction is required; proceeding without it would leave hidden old-tool instructions and dead code.

### Task 6 obsolete adapter deletion and stale guidance cleanup

- files deleted: `tools.py`, `schemas.py`, `hooks.py`, `role_policy.py`, `tests/test_tools_contract.py`.
- files rewritten around old guidance: `delegation.py`, `reconcile.py`, `verifier.py`, `prompts/reviewers/*.md`, `scripts/run_mini_benchmark.py`, `tests/test_prepare_delegations.py`, `tests/test_profile_verifiers.py`, `tests/test_verifier_independence.py`, `tests/test_hooks_reconcile.py`, `tests/test_plugin_registration.py`.
- active stale scan excluding `worknotes/`, `reference/`, caches: 0 hits for deleted adapter imports/schema names and the nine old `ponder_forge_*` direct tool names.
- focused command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cli_contract.py tests/test_plugin_registration.py tests/test_copy_install_smoke.py tests/test_prepare_delegations.py tests/test_profile_verifiers.py tests/test_verifier_independence.py tests/test_hooks_reconcile.py tests/test_mini_cases_static.py -q`.
- result: `21 passed`.
- redundancy check: no bridge tool, no hook compatibility layer, no role-policy shim, no old tool-handler test remains. `cli.py` is the single command surface and delegates algorithmic work to existing owner modules.
- confidence check: 100% confident Task 6 is complete at source focused-test level; moving to broad source and installed-copy verification.

### Task 7 source landing verification

- command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`.
- result: `38 passed`.
- command: `python3 -m compileall -q .`.
- result: exit 0, no output.
- active stale scan excluding `worknotes/`, `reference/`, caches: `hit_count 0`.
- command: `git diff --check -- ponder-forge`.
- result: exit 0, no output.
- confidence check: 100% confident source tree is internally consistent after pure CLI conversion; proceeding to installed-copy verification.

### Task 8 installed-copy verification

- copy-install command: `python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge`.
- copy-install result: `{"command_count": 1, "hook_count": 0, "installed": true, "is_symlink": false, "module_file": "/home/xu/.hermes/plugins/ponder_forge/__init__.py", "skill_count": 1, "target": "/home/xu/.hermes/plugins/ponder_forge", "tool_count": 0}`.
- installed test command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q` in `/home/xu/.hermes/plugins/ponder_forge`.
- installed test result: `38 passed`.
- installed compile command: `python3 -m compileall -q .` in `/home/xu/.hermes/plugins/ponder_forge`.
- installed compile result: exit 0, no output.
- installed CLI smoke: `HERMES_HOME=$(mktemp -d) python3 /home/xu/.hermes/plugins/ponder_forge/cli.py start --goal "research source notes" --profile auto` returned `success=true`, `profile=research`, `next_command=plan`, run `pf_run_d37edea68861`.
- source/installed hash comparison: `cli.py`, `__init__.py`, `commands.py`, `plugin.yaml`, `delegation.py`, `verifier.py`, `reconcile.py`, `scripts/run_mini_benchmark.py`, bundled skill, and key tests all `MATCH`.
- confidence check: 100% confident normal installed path is command+skill only with zero model-visible Ponder-Forge tools/hooks.

### Task 9 final closeout

- plan status: complete. Plan path: `worknotes/2026-07-04-skill-pure-cli-implementation-plan.md`.
- design audit status: complete. Design artifact path: `worknotes/tmp_skill_pure_cli_plan/design_audit.md`.
- implementation status: complete. Default Ponder-Forge plugin registration is command+skill only; `plugin.yaml` declares `provides_tools: []` and `provides_hooks: []`; obsolete direct-tool adapter files were deleted.
- source verification status: complete with `38 passed`, compileall exit 0, diff check exit 0, stale scan `hit_count 0`.
- installed-copy verification status: complete with copy smoke `tool_count=0`, `hook_count=0`, `command_count=1`, `skill_count=1`; installed tests `38 passed`; installed compileall exit 0; installed CLI smoke returned `success=true`.
- quest boundary: no commands wrote to `/home/xu/project/loop/DeepScientist/quests/001`.
- commit/push status: not executed because the implementation plan explicitly says no commit/push unless the user explicitly asks; this closeout leaves the working tree changed for review.
- confidence check: 100% confident the source and installed-copy implementation satisfy true skill + pure CLI. Remaining operational note: an already-running Hermes session may still have old hot-loaded tool definitions until restart/reload; installed copy is verified clean.

## Real CLI stability loop after pure CLI conversion

### Scope capture

- status: planning document for this real-run stability loop is not complete; 100% confidence is not justified yet.
- goal file reread: `worknotes/goal(禁止修改).md` lines 1-73 confirm the STAGE10 read-only quest task, Ponder-Forge-only edit boundary, immediate problems ledger updates, writing-plans repair planning, repeated real runs, and final confidence reporting requirements.
- installed smoke: `python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge` returned `tool_count=0`, `hook_count=0`, `command_count=1`, `skill_count=1`.
- installed CLI help/start smoke: `/home/xu/.hermes/plugins/ponder_forge/cli.py` exposes all required commands; temp-home `start` returned `success=true`, `profile=analysis`, `next_command=plan`.
- scratch created: `worknotes/tmp_real_cli_stability_20260704/` with `00_scope_requirements.md`, `01_size_inventory.md`, and `02_plugin_current_state_notes.md`.
- next action: read STAGE10 result/status files in small batches, write evidence notes, then finalize the real-run stability plan before launching the full Ponder-Forge workflow.

### Real-run planning complete

- Stage10 evidence notes written: `worknotes/tmp_real_cli_stability_20260704/03_stage10_evidence_notes.md` and `04_selector_gate_notes.md`.
- design audit written: `worknotes/tmp_real_cli_stability_20260704/05_design_audit.md`.
- final plan written: `worknotes/2026-07-04-real-cli-stability-loop-plan.md`.
- confidence review written: `worknotes/tmp_real_cli_stability_20260704/07_confidence_review.md`.
- structural check passed: 10 tasks, required paths present, code fences balanced, exact quest no-modification rule present, no vague planning terms from the configured scan.
- planning status: complete; 100% confident the plan is executable and bounded. Implementation/runtime confidence remains to be earned through real rounds.

### Real-run Task 1 install check

- installed copy refreshed with `python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge`.
- result: `installed=true`, `is_symlink=false`, `tool_count=0`, `hook_count=0`, `command_count=1`, `skill_count=1`.
- plugin enabled check: `hermes plugins list` shows `ponder-forge enabled`.
- installed CLI help exposes all required commands: `start`, `plan`, `delegations`, `submit-report`, `status`, `verify`, `gate`, `finalize`, `reconcile`.
- corrected source/installed hash check covered key files: `cli.py`, `plugin.yaml`, `planner.py`, `profiles.py`, `report_ingest.py`, `gates.py`, `store.py`, `verifier.py`, `renderer.py`, `reconcile.py`, `delegation.py`, and bundled skill; result `diff=[]`, `missing=[]`.
- note: two controller-side ad-hoc hash checks first referenced stale filenames `verification.py` and `finalizer.py`; those were invalid check inputs, not Ponder-Forge defects.

### Real-run Round 1 start/plan/delegations

- round dir: `worknotes/real_cli_rounds/round1/`.
- quest guard before manifest created at `round1/quest_guard_before.jsonl` for 12 authoritative Stage10 files.
- installed CLI `start` returned `success=true`, `profile=analysis`, `run_id=pf_run_353e985cf14a`, `next_command=plan`.
- installed CLI `plan` created five analysis tasks: `data_inspector`, `metric_analyst`, `reproduction_runner`, `sanity_reviewer`, `narrative_reviewer`.
- installed CLI `delegations` returned a native `delegate_task_payload`; controller summary initially counted the wrong key and printed `delegation_count=0`, so the actual payload is being reread before dispatch. This is a controller summary bug, not a plugin issue unless the payload is absent.
- reread confirmed `delegate_task_payload.tasks` contains five planned role tasks.
- dispatched 10 flat leaf subagents for Round 1: the five planned analysis roles plus gate boundary, theory/ablation, claim attack, next-steps, and CLI-ergonomics observers.
- subagent report target: `worknotes/real_cli_rounds/round1/workers/*.md`; quest path remains read-only.
- while subagents are pending, controller will only run non-final probes and prep; no finalize/final completion claim before worker reports are returned and read.
- installed CLI pre-report probes: `status` returned success, and `gate` returned `blocked` before any critical reports, which is expected.
- controller metric snapshot first failed because the ad-hoc read-only Python command used stale JSON keys `hard_failure_count` and `seed_robustness_rows`; actual keys are `hard_failures` and `seed_robustness_row_count`. This was controller command error, not a plugin defect; corrected snapshot follows.
- corrected controller metric snapshot succeeded: downstream gate `closed`, downstream run `false`, large eval endpoint rows `360/360`, hard failures `0`, recovery endpoint rows `1380`, seed robustness rows `252`, selector count `6`.
- report/verify schema prep: read installed source/tests for `report_ingest`, `verifier`, `gates`, `renderer`, and CLI contract; Round 1 reports will be parent-curated JSON with critical `data_result` assertions plus `metric_output.command`, `exit_code`, `sanity_check`, and `reproduction_log`/`transform_script` evidence.
- report drafts are staged only in `round1/reports/README.md` and `controller_report_draft_notes.md`; no report submission will occur until worker reports are returned and read.

### Real-run Round 1 worker recovery / wave2 dispatch

- first worker report sweep found 3/10 wave1 reports written: `sanity_reviewer.md`, `narrative_reviewer.md`, `stage10_claim_attack_reviewer.md`.
- 7/10 wave1 reports still missing at that sweep: `data_inspector`, `metric_analyst`, `reproduction_runner`, `stage10_gate_boundary_reviewer`, `stage10_theory_ablation_reviewer`, `stage10_next_steps_planner`, `ponder_cli_operator_observer`.
- read the 3 returned reports. All agree Stage10 must be reported as a conservative/gate-bounded evidence package and must not claim downstream utility, oral readiness, broad model-family generality, CE selector success, universal recovery, or conclusive mechanism proof.
- dispatched wave2 with 10 additional leaf workers, bringing total subagents to the requested cap of 20. Wave2 covers installed CLI happy path, error paths, lifecycle idempotency, reconcile, report schema ergonomics, bundled skill guidance, installed packaging, profile/gate matrix, state files, and quest guard audit.
- wave2 workers are forbidden to mutate quest/source/live run; any CLI run must use isolated temp `HERMES_HOME`; controller must reproduce any claimed plugin defect before logging it in `problems.md`.

### PF-REAL-009 repair planning

- issue logged: `problems.md` PF-REAL-009.
- real trigger: Round 1 installed `delegations` payload for `pf_run_353e985cf14a`; child context omitted report schema, `data_result`/`critical` gate hints, role duties, and duplicated required evidence text.
- parent reproduction: first child context had `required_evidence_occurrences=2`, `has_json_skeleton=False`, `has_data_result_hint=False`, `has_critical_hint=False`, `has_role_specific_data_inspector=False`.
- design audit: `worknotes/tmp_pf_real_009_delegation_contract/02_design_audit.md`.
- repair plan: `worknotes/pf_real_009_delegation_child_contract_repair_plan.md`.
- confidence review: `worknotes/tmp_pf_real_009_delegation_contract/03_confidence_review.md`.

### PF-REAL-009 source implementation

- RED proof: `tests/test_prepare_delegations.py` failed because context duplicated `Required evidence types:` and lacked child report contract fields.
- implementation: patched `delegation.py` to emit a compact child JSON contract, analysis `data_result`/`critical` gate guidance, role duties for analysis roles, and duplicate evidence-line filtering.
- documentation: patched bundled `resources/skills/ponder-forge-usage/SKILL.md` with a manual child report contract while preserving CLI-first/no-direct-tool guidance.
- source verification: focused prepare-delegations tests `4 passed`; full source tests `39 passed`; `python3 -m compileall -q .` exit 0.
- source payload inspection: `required_evidence_occurrences=1`, `has_json_skeleton=True`, `has_data_result_hint=True`, `has_critical_hint=True`, `has_role_specific_data_inspector=True`, context length `2058`.

### PF-REAL-009 installed verification

- installed copy refreshed with `python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge`; result remained pure CLI/skill: `tool_count=0`, `hook_count=0`, `command_count=1`, `skill_count=1`.
- installed-copy tests: `39 passed`.
- installed-copy compileall: exit 0.
- fresh installed CLI temp-home validation run `pf_run_f9bc1919aa2a`: five analysis roles generated; first child context had `required_evidence_occurrences=1`, `has_json_skeleton=True`, `has_data_result_hint=True`, `has_critical_hint=True`, `has_role_specific_data_inspector=True`, and `has_direct_tool_name=False`.
- PF-REAL-009 status: closed in source and installed copy. Current Round 1 is a defect-discovery run and does not count as clean; clean-round count restarts after this fix.

### PF-REAL-009 commit/push

- commit: `c531bd4 fix: strengthen ponder-forge delegation contracts`.
- pushed to `origin/main`.
- commit scope: Ponder-Forge source, bundled skill, tests, `note.md`, `problems.md`, and PF-REAL-009 repair plan/scratch notes.
- next action: start fresh installed real clean round #1 after PF-REAL-009.

### post-PF-REAL-009 clean round #1

- round dir: `worknotes/real_cli_rounds/post_pf009_clean1/`.
- run_id: `pf_run_f6eb0cb396a3`.
- installed CLI workflow completed: `start`, `plan`, `delegations`, `submit-report` x3, `verify` task creation/verdict x3, `status`, `gate`, `finalize` twice, `reconcile`, and late submit rejection.
- delegation contract check: `required_evidence_occurrences=1`, schema/data_result/critical/role hints present, no direct-tool name in child context.
- gate: `passed`; critical assertions 3/3 supported and accepted; independent/artifact/final trace coverage all `1.0`; blocking gaps `0`.
- finalization: final status `final` twice; final report hash idempotent.
- lifecycle: late submit returned nonzero with `success=false`; reconcile returned success with empty repair/orphan lists.
- quest guard: 12 key Stage10 files unchanged by size, mtime, and sha256.
- clean streak after PF-REAL-009: 1.

### post-PF-REAL-009 clean rounds #2 and #3

- clean round #2 dir: `worknotes/real_cli_rounds/post_pf009_clean2/`, run_id `pf_run_bbb19dd9962e`.
- clean round #3 dir: `worknotes/real_cli_rounds/post_pf009_clean3/`, run_id `pf_run_1f991fba39cd`.
- both rounds completed installed CLI `start`, `plan`, `delegations`, `submit-report` x3, `verify` task creation/verdict x3, `status`, `gate`, `finalize` twice, `reconcile`, late submit rejection, and quest before/after guard.
- both rounds: delegation contract check passed (`required_evidence_occurrences=1`, schema/data_result/critical/role hints present, no direct-tool name).
- both rounds: `gate=passed`, critical assertions 3/3 supported/accepted, independent/artifact/final trace coverage all `1.0`, blocking gaps `0`.
- both rounds: final report idempotent, late submit rejected with `success=false`, reconcile returned success with no repairs/orphans, and quest guard unchanged.
- clean streak after PF-REAL-009: 3.
- next action: process remaining wave1/wave2 subagent reports before final closeout; do not declare final completion while delegated audits are unhandled.

### wave2 parent reproductions reset the clean streak

- parent reproduction file: `worknotes/real_cli_rounds/round1/parent_reproductions_after_wave2.json`.
- confirmed: missing required CLI arg is non-JSON; `reconcile` unknown run returns `success=true`; `status` after completed final still says `next_required_action="finalize"`; analysis gate passes `metric_output.exit_code=1`; coding delegation contract contains `<profile_assertion_type>` and analysis evidence examples.
- parent matrix reproduction file: `worknotes/real_cli_rounds/round1/parent_profile_gate_matrix_repro.json`.
- confirmed: coding `root_cause_trace + failing_test(exit_code=1)` passes; math `proof_check` passes while unadvertised; math resolved/negative counterexample-search evidence blocks.
- problems logged as PF-REAL-010..015 in `worknotes/problems.md`.
- plan: `worknotes/pf_real_010_015_contract_consistency_repair_plan.md`; design audit in `worknotes/tmp_pf_real_010_015_contract_consistency/01_design_audit.md`.
- clean streak after PF-REAL-009 is no longer valid for final closeout; restart from 0 after PF-REAL-010..015 are fixed and installed.

### PF-REAL-010..015 source fix status

- RED: focused source suite reproduced 9 failures across CLI status/envelope, reconcile, analysis/coding/math gates, profile vocabulary, and coding delegation contract.
- GREEN: focused source suite `tests/test_cli_contract.py tests/test_hooks_reconcile.py tests/test_gates_profiles.py tests/test_profiles.py tests/test_prepare_delegations.py -q` -> `25 passed`.
- full source suite: `46 passed`; source `compileall` exit 0.
- source temp-home smoke confirmed missing CLI arg is JSON, reconcile unknown run fails JSON, and coding delegation contract now has `code_claim`, no placeholder, and no `metric_output` leakage.
- installed copy refresh started after this source verification; clean streak remains 0 until installed validation and fresh real rounds pass.

### PF-REAL-010..015 installed fix status

- bundled skill was also patched so usage docs match the runtime contract: no direct tools/hooks, profile-specific child report anchors, reviewer payload loop, `status.next_required_action="complete"`, and reconcile limited to stale/orphan retry payloads.
- source after skill patch: focused suite with mini/static tests `29 passed`; full source suite `46 passed`; source compileall exit 0.
- installed copy refreshed again after skill patch: copy smoke returned `tool_count=0`, `hook_count=0`, `command_count=1`, `skill_count=1`; installed skill equals source and contains `code_claim`, terminal complete status guidance, and no direct hooks/tools wording.
- installed verification: full installed suite `46 passed`; installed compileall exit 0.
- installed final reproduction: `worknotes/real_cli_rounds/post_pf010_015_installed_repro_final.json` confirms missing CLI arg JSON envelope, reconcile unknown run failure, analysis `exit_code=1` blocked, analysis `exit_code=0` passed and status terminal `complete`, coding failing-test-only blocked, math resolved counterexample-search passed, and coding delegation contract is profile-specific.
- problems PF-REAL-010..015 closed in `worknotes/problems.md`; clean streak reset to 0 after this final install.

### PF-REAL-016 packaging cleanup

- wave2 installed packaging audit noted installed copy included `worknotes/`; this is packaging cleanliness/privacy noise, not a runtime CLI failure, but it should be fixed before final install confidence.
- PF-REAL-016 logged in `worknotes/problems.md`.
- test added: `tests/test_copy_install_smoke.py` asserts copied target has no `worknotes/`.
- source change: `scripts/copy_install_smoke.py` now excludes `worknotes` from install copies.
- clean streak after PF-REAL-010..015 is superseded by this packaging change; restart after PF-REAL-016 install verification.

### PF-REAL-016 installed fix status

- source verification: focused suite including copy-install/static/CLI/gate/delegation tests `30 passed`; full source suite `46 passed`; source compileall exit 0.
- installed copy refreshed after PF-REAL-016: copy smoke returned `tool_count=0`, `hook_count=0`, `command_count=1`, `skill_count=1`.
- installed copy now has `worknotes_exists=false`; runtime skill/tests remain installed.
- installed verification: full installed suite `46 passed`; installed compileall exit 0; temp-home installed smoke confirmed missing arg JSON, profile-specific analysis delegation, no direct-tool string, and `installed_worknotes=false`.
- PF-REAL-016 closed in `worknotes/problems.md`; final clean streak starts after this install.

### final post-PF-REAL-016 clean streak

- final clean summary: `worknotes/real_cli_rounds/post_pf016_clean_summary.json`.
- clean round #1: `post_pf016_clean1`, run `pf_run_ebdb28c7b36b`.
- clean round #2: `post_pf016_clean2`, run `pf_run_2ce6694c55c8`.
- clean round #3: `post_pf016_clean3`, run `pf_run_8b02996ca00c`.
- each final clean round used installed CLI with isolated persistent `HERMES_HOME` under that round dir, read the real quest Stage10 artifacts, and wrote no quest files.
- each final clean round exercised `submit-report` missing-arg JSON error, `start`, `plan`, `delegations`, five `submit-report` calls, independent-review task creation, five accepted verdicts, `status`, `gate`, `finalize` twice, post-final `status`, `reconcile`, unknown-run `reconcile`, late-submit rejection, final-report idempotency, installed packaging `worknotes` absence, and quest before/after guards.
- all three final rounds: `gate=passed`, `critical_count=5`, independent/artifact/final trace coverage all `1.0`, `status_after.next_required_action="complete"`, late submit rejected, unknown reconcile rejected, missing-arg error JSON, installed `worknotes` absent, and quest guard unchanged.
- all 20 worker reports landed and are synthesized in `worknotes/real_cli_rounds/round1/worker_reports_final_synthesis.md`; no unhandled blocking plugin issue remains.
