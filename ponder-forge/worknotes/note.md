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
