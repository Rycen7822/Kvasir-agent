# Ponder-Forge Real-Run Problems Ledger

- started_at: 2026-07-04T03:51:33+08:00
- source_dir: `/home/xu/project/autosci-delphi/ponder-forge`
- installed_dir: `/home/xu/.hermes/plugins/ponder_forge`
- real_task_path: `/home/xu/project/loop/DeepScientist/quests/001`
- real_task_guardrail: read-only analysis; do not modify quest code or documents.
- real_task: deeply understand the quest project, analyze STAGE10 results, and produce next-step improvement recommendations.

## Live problem log

### PF-REAL-001 — Hermes tool dispatch passes `task_id` kwarg to Ponder-Forge handlers

- status: Closed in installed fresh-process probe; current TUI session still has stale pre-fix handler until reset/restart.
- discovered_at: 2026-07-04T03:51:33+08:00
- real trigger: Round 1 attempted native `ponder_forge_start` for the STAGE10 read-only analysis task.
- observed failure: `TypeError: ponder_forge_start() got an unexpected keyword argument 'task_id'`.
- impact: severe blocker; the plugin is enabled and visible, but current registered tool handlers cannot be called by Hermes in this real session.
- suspected root cause: `__init__.py` registers `HANDLERS[name]` directly, while `tools.py` handlers accept only `args`; Hermes passes dispatch metadata kwargs such as `task_id`.
- root cause: `__init__.py` registered raw one-argument handlers; Hermes dispatch passes metadata kwargs.
- fix: added a narrow registration adapter in `__init__.py` and a regression that calls registered handlers with `task_id`/`tool_call_id` kwargs.
- verification: focused tests `7 passed`; full tests `36 passed`; copy install smoke succeeded; fresh installed plugin registration probe returned 9 tools / 6 hooks / 1 command / 1 skill and `metadata_kwargs_ok=true`.
- remaining boundary: this already-running TUI session still holds the stale handler object, so direct in-session `ponder_forge_start` remains stale until reset/restart. Round 1 continues through a fresh installed plugin process for Ponder-Forge state/payload generation.


## Suspected / observation queue

- The quest path is writable by the OS account, so every Ponder-Forge child prompt must explicitly forbid writes under `/home/xu/project/loop/DeepScientist/quests/001`.

### PF-REAL-002 — Delegation payload omits the real run goal and constraints

- status: Closed in installed payload regeneration.
- discovered_at: 2026-07-04T03:56:08+08:00
- real trigger: Round 1 fresh installed plugin generated `round1_ponder_forge_payload.json` for the STAGE10 task.
- observed failure: `delegate_task_payload.tasks[*].context` only contains generic profile/role/evidence instructions; it does not include the user goal, quest path, or read-only constraint.
- impact: severe blocker; native child agents would not know the actual project path or analysis objective, so the real task cannot be executed faithfully.
- root cause: `planner.py` stores role tasks with generic context only; `delegation.py` forwards task context and profile evidence requirements but not `runs.user_goal` or `runs.config_json.constraints`.
- fix: `delegation.py` now injects `runs.user_goal` and `config_json.constraints` into every child context; `tests/test_prepare_delegations.py` asserts both are present.
- verification: focused delegation tests `2 passed`; full tests `36 passed`; copy install smoke succeeded; regenerated installed payload `worknotes/round1_retry_ponder_forge_payload.json` contains the quest path and READ ONLY constraint in every child context.

### PF-REAL-003 — Final report is too thin for a real complex task

- status: Closed in source and installed copy; Round 2 will prove on a fresh real run.
- discovered_at: 2026-07-04T04:10:04+08:00
- real trigger: Round 1 finalized run `pf_run_5886197fa2aa` after accepted independent review.
- observed failure: `/home/xu/.hermes/ponder_forge/runs/pf_run_5886197fa2aa/final.md` only contains one accepted assertion bullet; it does not include evidence source refs, artifact paths, or verifier verdict trace.
- impact: not a gate blocker, but a real-task usability defect. The final artifact is too sparse to be the durable answer for a complex Stage10 analysis task, even though the graph contains the evidence.
- root cause: `renderer.py` rendered final statements but did not project accepted assertion evidence/artifacts/verdict trace into Markdown.
- fix: `renderer.py` now renders compact evidence, artifact, and verifier verdict trace for linked accepted assertions.
- verification: focused renderer test passed; public tool chain test passed; full source tests `36 passed`; compileall passed; copy install smoke succeeded; installed-copy tests `36 passed`; installed-copy compileall passed.

### PF-REAL-004 — Completed runs can be polluted by late child reports

- status: Closed in source and installed copy; Round 2 will prove with a fresh real run.
- discovered_at: 2026-07-04T04:12:00+08:00
- real trigger: after Round 1 reached `gate_status=passed` and `final_status=final`, the background child agents eventually submitted reports for stale task ids.
- observed failure: the same completed run `pf_run_5886197fa2aa` changed from gate passed to gate blocked because late unverified critical assertions were added after finalization.
- impact: severe stability defect. A finalized run is not immutable; late async reports can invalidate an already delivered final artifact and make repeated finalize/gate calls inconsistent.
- root cause: `ponder_forge_report_submit` mutated runs regardless of run status; `ponder_forge_finalize` re-evaluated completed runs instead of returning stored final artifacts idempotently.
- fix: `ponder_forge_report_submit` now rejects completed runs before mutation; `ponder_forge_finalize` now returns stored final Markdown/artifact paths idempotently for completed runs.
- verification: public tool chain lifecycle test passed; full source tests `36 passed`; compileall passed; copy install smoke succeeded; installed-copy tests `36 passed`; installed-copy compileall passed.

### PF-REAL-005 — Analysis metric gate has hidden `command` requirement

- status: Closed in source and installed copy; Round 2 retry will prove with a fresh real run.
- discovered_at: 2026-07-04T04:24:00+08:00
- real trigger: Round 2 fresh Hermes `metric_analyst` child wrote `worknotes/round2_metric_analyst_report.md` and successfully submitted report `pf_report_2d5f07e8d4ce` with assertion `pf_assertion_ecfdb026e84c`.
- observed failure: gate blocked with `critical assertion lacks required profile evidence` even though the submitted evidence types were `metric_output`, `transform_script`, and `sanity_check`.
- root cause: analysis gate requires at least one `metric_output` evidence item with a non-empty `command`, but `prepare_delegations`/child instructions only listed evidence types and did not expose that profile-specific field requirement.
- impact: real child reports can look structurally compliant and submit successfully while still failing the gate for a hidden rule.
- fix: delegation contexts now state the analysis profile requirement that at least one `metric_output` evidence item must include a non-empty `command` and `exit_code`; gate gaps now include `profile_specific_reason` mentioning `metric_output.command`.
- verification: focused PF-REAL-005 tests passed; prepare/gate tests passed; full source tests `38 passed`; compileall passed; copy install smoke succeeded; installed-copy tests `38 passed`; installed-copy compileall passed.

## Superseded stability closeout

- PF-REAL-001..005 are closed in source and in the installed copy at `/home/xu/.hermes/plugins/ponder_forge`.
- Clean pass #1 after the last fix: Round 2 retry run `pf_run_97ba23c5ffc5` reached `gate=passed` and `final_status=final`, rendered evidence/artifact/verdict traces, rejected a late report on completed run, and preserved final report hash.
- Clean pass #2 after the last fix: Round 3 run `pf_run_6fa8a73606e2` reached `gate=passed` and `final_status=final`, rendered evidence/artifact/verdict traces, rejected a late report on completed run, and preserved final report hash.
- This closeout was superseded by PF-REAL-006, PF-REAL-007, and PF-REAL-008 discovered during continued real-task running.

### PF-REAL-006 — `report_submit` silently accepts alias-shaped reports and drops evidence

- status: Closed in source and installed copy.
- discovered_at: 2026-07-04T05:31:44+08:00
- real trigger: Round 4 fresh run `pf_run_496b1615dbc7` used the public `ponder_forge_report_submit` tool from the current Hermes tool surface for the Stage10 read-only analysis task.
- observed failure: a controller report using intuitive keys (`assertions[*].type`, `assertions[*].statement`, top-level `evidence`, and `artifacts[*].kind`) returned `success=true` but created `evidence_ids=[]`; gate then reported `missing_critical_assertion` because assertions had default type/text instead of the intended `data_result` statement.
- impact: severe report-format stability defect. A real agent can believe a structured report was accepted while Ponder-Forge silently drops evidence and later blocks or misdiagnoses the gate.
- root cause: public tool schema is `additionalProperties: true`, while `report_ingest.py` only consumes exact nested fields (`assertion_type`, `text`, `assertions[*].evidence`, `evidence_type`, `source_ref`, `quote_or_observation`, `artifact_type`). There is no normalization or validation for common alias-shaped payloads.
- fix plan: write `worknotes/pf_real_006_repair_plan.md`; then add narrow report normalization/validation at the `report_ingest.py` owner seam, with tests proving alias payloads ingest evidence and malformed reports fail loudly.
- current run status: Round 4 first attempt does not count as clean. Restart after PF-REAL-006 is fixed and installed; clean-pass count resets after this new defect.
- real impact confirmed after delegate results returned: `pf_run_496b1615dbc7` contains 7 reports / 29 assertions / 6 evidence items, but gate remains blocked because fix-before reports created unsupported critical assertions with no attached evidence; `reconcile` cannot safely infer missing evidence. This polluted run is intentionally not counted as clean. The fix prevents new alias-shaped reports from entering that state by normalizing evidence or failing loudly before mutation.
- fix implemented: `report_ingest.py` normalizes `type`/`statement`/top-level `evidence`/`kind` aliases and rejects unlinked or missing `evidence_refs`; tests cover success and failure paths.
- source verification: report-ingest focused tests passed, public/gate tests passed, full source tests passed, compileall passed.
- install verification: copy-install smoke succeeded; installed-copy full tests passed; fresh installed alias smoke created 2 evidence rows and rejected unlinked evidence.
- post-fix real verification: after PF-REAL-008 final install, three consecutive fresh installed real-task rounds passed using both alias and canonical report formats: `pf_run_1f1b9c2ef2b7`, `pf_run_29228431433a`, `pf_run_c0f170979d4d`.

### PF-REAL-007 — Full test suite depended on ignored worknotes fixture

- status: Closed in source and installed copy.
- discovered_at: 2026-07-04T05:35:00+08:00
- real trigger: after cleaning old intermediate worknotes, full source tests failed at `test_smoke_report_template_exists_and_has_metrics` because `worknotes/ponder_forge_smoke_report_template.md` had been archived/deleted.
- observed failure: `FileNotFoundError` for a test fixture under `ponder-forge/worknotes/`, while `.gitignore` ignores that directory.
- impact: clean checkouts or cleaned workspaces cannot reliably run the full Ponder-Forge suite; this undermines repeatable verification after real-run fixes.
- root cause: a static smoke template fixture lived under ignored scratch/worknotes instead of tracked test data.
- fix plan: `worknotes/pf_real_007_repair_plan.md`.
- fix: moved the template content to tracked `tests/fixtures/ponder_forge_smoke_report_template.md`, updated `tests/test_mini_cases_static.py`, and removed the ignored worknotes copy.
- verification: `tests/test_mini_cases_static.py` -> `3 passed`; full source suite -> `43 passed`; installed-copy suite -> `43 passed`.

### PF-REAL-008 — `gate_status` metrics reported placeholder coverage values

- status: Closed in source and installed copy.
- discovered_at: 2026-07-04T05:54:27+08:00
- real trigger: post-PF-REAL-006 clean run `pf_run_e4ccb5bd3af5` reached `gate_status=passed`, but the returned metrics still reported `independent_review_coverage=0.0`, `artifact_reproducibility_coverage=0.0`, and `final_statement_trace_coverage=0.0`.
- observed failure: gate pass/fail was correct, but status metrics were misleading; `unsupported_critical_assertions` also counted gaps instead of critical assertions, so a single bad assertion could inflate the count.
- impact: operator-facing gate status was not trustworthy enough for long-running stability decisions, even when finalize was correct.
- root cause: `gates.py` returned placeholder coverage metrics and used `len(gaps)` for an assertion-count metric.
- fix plan: `worknotes/pf_real_008_repair_plan.md`.
- fix: `evaluate_gate` now computes supported critical assertion count, true unsupported critical assertion count, blocking gap count, independent review coverage, artifact-backed coverage, and final-statement trace coverage from existing graph rows.
- verification: RED tests reproduced the placeholder/inflated-count failures; focused gate tests -> `7 passed`; full source suite -> `43 passed`; installed-copy suite -> `43 passed`; post-fix real clean rounds showed all three coverage metrics at `1.0` and zero blocking gaps.

## Final stability closeout

- PF-REAL-001..008 are closed in source and in the installed copy at `/home/xu/.hermes/plugins/ponder_forge`.
- Final clean pass #1 after the last fix: `round4_retry_clean` run `pf_run_1f1b9c2ef2b7`, alias-shaped report payload, `gate=passed`, `final_status=final`, late report rejected, gate coverage metrics all `1.0`.
- Final clean pass #2 after the last fix: `round5_clean` run `pf_run_29228431433a`, canonical nested report payload, `gate=passed`, `final_status=final`, late report rejected, gate coverage metrics all `1.0`.
- Final clean pass #3 after the last fix: `round6_clean` run `pf_run_c0f170979d4d`, alias-shaped report payload, `gate=passed`, `final_status=final`, late report rejected, gate coverage metrics all `1.0`.
- Quest key-file guard: the final clean-run script compared size, mtime, and sha256 for nine Stage10 files before and after all three rounds; `quest_key_files_unchanged=true`.

### PF-REAL-009 — Delegation child context is not enough to produce parent-submittable reports

- status: Closed in source and installed copy; clean-round count resets after this fix.
- discovered_at: 2026-07-04T07:11:35+08:00 during the resumed real STAGE10 run.
- real trigger: Round 1 run `pf_run_353e985cf14a` generated installed CLI `delegations` payload for the read-only STAGE10 analysis task, then wave1 child reports started returning as Markdown rather than parent-submittable JSON.
- observed failure: the generated child context says only `Return a structured JSON report ... with run_id, task_id, role, summary, assertions, evidence, and artifacts where applicable`; it omits an exact JSON skeleton, accepted assertion/evidence/artifact field names, top-level `evidence_refs` rules, profile-critical `data_result`/`critical` requirements, and role-specific duties. It also repeats `Required evidence types: dataset, transform_script, metric_output, sanity_check, plot_artifact, reproduction_log.` twice.
- parent reproduction: parsing `worknotes/real_cli_rounds/round1/delegations.json` found `required_evidence_occurrences=2`, `has_json_skeleton=False`, `has_data_result_hint=False`, `has_critical_hint=False`, and `has_role_specific_data_inspector=False`.
- independent worker evidence: `workers/ponder_cli_operator_observer.md` lines 28-157 identifies the same blocker and proposes minimal fixes: embed schema skeleton, profile-specific critical gate hints, role-duty lines, de-duplicate evidence text, and clarify child output channel.
- impact: real child agents can produce useful prose but not reliably produce JSON that `submit-report` ingests and `gate` accepts. The parent must manually repair reports, which weakens long-run stability for complex real tasks.
- suspected root cause: `planner.py` stores the same generic `Required evidence types` line in every task, and `delegation.py` also appends the same profile evidence line while giving only a prose description of the report contract.
- required fix boundary: patch only the delegation/planning instruction owner seam and tests; do not add new runtime surfaces unless the plan proves the existing CLI/help path cannot carry the contract.
- root cause: `delegation.py` assembled child context from generic prose and duplicated `planner.py` task context; it did not expose the report-ingest schema, profile-critical assertion expectations, or role-specific duties.
- fix plan: `worknotes/pf_real_009_delegation_child_contract_repair_plan.md`.
- fix implemented: `delegation.py` now emits a compact child JSON contract, analysis `data_result`/`critical` gate guidance, role duties for analysis roles, and duplicate evidence-line filtering; bundled skill now includes the manual child report contract.
- source verification: focused prepare-delegations tests `4 passed`; full source tests `39 passed`; compileall exit 0; source payload inspection showed `required_evidence_occurrences=1`, `has_json_skeleton=True`, `has_data_result_hint=True`, `has_critical_hint=True`, and `has_role_specific_data_inspector=True`.
- install verification: copy-install smoke returned `tool_count=0`, `hook_count=0`, `command_count=1`, `skill_count=1`; installed-copy tests `39 passed`; installed compileall exit 0; fresh installed CLI temp-home `delegations` inspection showed `required_evidence_occurrences=1`, schema/data_result/critical/role hints present, and no direct-tool name in context.

### PF-REAL-010 — Missing required CLI arguments bypass the JSON error envelope

- status: Closed in source and installed copy; clean-round count reset after this fix.
- discovered_at: 2026-07-04T07:26:04+08:00 during wave2 installed CLI error-path audit and parent reproduction.
- real trigger: `wave2_cli_error_paths_temp_home.md` ran installed `submit-report` without `--file` while auditing the real Ponder-Forge CLI surface.
- observed failure: `submit-report` without required `--file` exits `2`, writes argparse usage to stderr, and writes no JSON to stdout.
- parent reproduction: `worknotes/real_cli_rounds/round1/parent_reproductions_after_wave2.json` records `missing_file_arg.returncode=2`, `stdout=""`, and `json_error=JSONDecodeError(...)`.
- impact: automation that treats Ponder-Forge CLI failures as JSON cannot parse this common argument-validation failure.
- root cause: argparse calls `ArgumentParser.error()`/`SystemExit` before `main()` can wrap the failure in `_err(...)`.
- required fix boundary: keep human `--help` behavior; make argument-validation errors emit the same JSON envelope as runtime failures.
- fix: `JsonArgumentParser.error()` raises into the CLI JSON envelope while preserving normal help behavior.
- verification: focused source suite `25 passed`, full source suite `46 passed`, installed-copy suite `46 passed`, installed final reproduction shows `missing_arg_json=true` and empty stderr.

### PF-REAL-011 — `reconcile` reports success for unknown run ids

- status: Closed in source and installed copy; clean-round count reset after this fix.
- discovered_at: 2026-07-04T07:26:04+08:00 during wave2 reconcile audit and parent reproduction.
- real trigger: installed CLI `reconcile --run-id pf_run_unknown_parent_repro --stale-after-seconds 0`.
- observed failure: command returns exit `0` and `{"success": true, ...}` even though the run id does not exist.
- parent reproduction: `parent_reproductions_after_wave2.json` records `reconcile_unknown.json.success=true` for the unknown run.
- impact: operators can mistake a typo or stale run id for a successful reconciliation.
- root cause: `reconcile_run()` iterates zero tasks and returns a no-op payload without validating `store.get_run(run_id)`.
- required fix boundary: use the same unknown-run failure semantics as `plan`, `status`, `gate`, and `finalize`.
- fix: `reconcile_run()` validates `store.get_run(run_id)` before no-op/retry logic.
- verification: focused/source/installed tests passed; installed final reproduction shows `reconcile_unknown_success=false`.

### PF-REAL-012 — `status` keeps asking for `finalize` after a run is already completed

- status: Closed in source and installed copy; clean-round count reset after this fix.
- discovered_at: 2026-07-04T07:26:04+08:00 during wave2 happy-path audit and parent reproduction.
- real trigger: after a temp-home installed run finalized successfully, `status --run-id ...` was called again.
- observed failure: status returned `gate_status="passed"` and `next_required_action="finalize"` even though the run status was completed and final artifacts already existed.
- parent reproduction: `parent_reproductions_after_wave2.json` records `status_after_final.json.next_required_action="finalize"`.
- impact: controller loops can re-finalize unnecessarily or treat a completed run as unfinished.
- root cause: `cmd_status()` derives `next_required_action` only from current gate state and ignores the persisted completed run/final report state.
- required fix boundary: preserve the existing `verify`/`finalize` actions before completion; return an explicit terminal action for completed/final runs.
- fix: `cmd_status()` now returns `run_status` and terminal `next_required_action="complete"` when a completed run has final report artifacts.
- verification: focused/source/installed tests passed; installed final reproduction shows `status_after_final_next="complete"`.

### PF-REAL-013 — Analysis gate accepts failed metric commands despite requiring `exit_code`

- status: Closed in source and installed copy; clean-round count reset after this fix.
- discovered_at: 2026-07-04T07:26:04+08:00 during wave2 profile/gate audit and parent reproduction.
- real trigger: parent submitted an analysis `data_result` with `metric_output.command="python eval.py"` and `exit_code=1`, plus `transform_script` and `sanity_check`, then accepted the independent review.
- observed failure: `gate` returned `status="passed"` and `finalize_allowed=true`.
- parent reproduction: `parent_reproductions_after_wave2.json` records `analysis_exit_code_1_gate.gate.status="passed"` and a final report preserving the failed metric output.
- impact: a failed computation can satisfy the computation-provenance gate, contradicting the child guidance that says `metric_output` needs `command` and `exit_code`.
- root cause: `_profile_specific_gap("analysis", evidence)` checks only that a `metric_output` has a non-empty `command`; it ignores missing/nonzero `exit_code`.
- required fix boundary: require at least one analysis `metric_output` with a non-empty command and successful exit code; add a regression for nonzero/missing exit code.
- fix: analysis profile-specific gate now requires a `metric_output` item with non-empty `command` and `exit_code=0`.
- verification: focused/source/installed tests passed; installed final reproduction shows `analysis_exit_code_1_gate="blocked"` and `analysis_exit_code_0_gate="passed"`.

### PF-REAL-014 — Delegation report contract is analysis-shaped for non-analysis profiles and retry payloads

- status: Closed in source and installed copy; clean-round count reset after this fix.
- discovered_at: 2026-07-04T07:26:04+08:00 during wave2 report-schema/profile audit and parent reproduction.
- real trigger: parent created a coding-profile run and inspected installed `delegations` output.
- observed failure: the coding child context contained `"assertion_type": "<profile_assertion_type>"` and analysis evidence examples (`metric_output`, `sanity_check`, `reproduction_log`) instead of the coding `code_claim` and coding evidence groups.
- parent reproduction: `parent_reproductions_after_wave2.json` records `contains_placeholder=true`, `contains_metric_output=true`, and `contains_code_claim=false` for the coding delegation contract.
- related wave2 finding: `wave2_report_schema_ergonomics.md` also showed reconcile retry payloads use a thinner context than first-wave delegations.
- impact: non-analysis child agents can follow the prompt exactly and still produce reports that fail the profile gate or require parent repair.
- root cause: `_report_contract(profile_id)` only special-cases analysis and otherwise emits a placeholder plus hard-coded analysis-style evidence examples; `reconcile._retry_payload()` separately constructs a thin retry prompt.
- required fix boundary: generate the report contract from `ProfileSpec` for every profile and reuse the same child-context builder for first-wave and retry/orphan payloads.
- fix: `delegation.py` now builds child contexts from `ProfileSpec`, emits profile-specific assertion/evidence examples, and exports the same builder for reconcile retry payloads; bundled skill now documents profile anchors and reviewer/reconcile status boundaries.
- verification: focused/source/installed tests passed; installed final reproduction shows coding context has `code_claim`, no placeholder, no `metric_output` leakage, and `passing_test` guidance.

### PF-REAL-015 — Profile gate matrix admits or rejects evidence inconsistently with its own vocabulary

- status: Closed in source and installed copy; clean-round count reset after this fix.
- discovered_at: 2026-07-04T07:26:04+08:00 during wave2 profile/gate matrix audit and parent reproduction.
- real triggers and parent reproductions:
  - `worknotes/real_cli_rounds/round1/parent_profile_gate_matrix_repro.json` records coding `root_cause_trace + failing_test(exit_code=1)` gate status `passed`.
  - The same repro records math `proof_step + proof_check` gate status `passed` even though `proof_check` is not advertised in `math.required_evidence_types`.
  - The same repro records math `proof_step + critique + counterexample(resolved=true)` gate status `blocked` with `math proof gate has unresolved counterexample evidence`.
- impact: profile gates are not trustworthy enough for complex non-analysis tasks: coding can finalize with only failing proof, math can pass on unadvertised vocabulary, and math can block negative/resolved counterexample-search evidence.
- root cause: profile required groups and profile-specific gaps are too coarse: coding treats `failing_test` as sufficient execution proof; math accepts `proof_check` without advertising it and treats any `counterexample` evidence as unresolved regardless of payload metadata.
- required fix boundary: patch only clear contract mismatches now. Require successful coding execution evidence for coding gates; advertise `proof_check`; make math counterexample blocking inspect unresolved/positive counterexample evidence instead of the token alone; add gap types for operator diagnostics.
- fix: coding gates require successful `passing_test` or `execution_log.exit_code=0`; math advertises `proof_check`; math counterexample blocking distinguishes positive/unresolved counterexamples from resolved/negative search evidence; profile-evidence gaps include `gap_type`.
- verification: focused/source/installed tests passed; installed final reproduction shows coding failing-test-only gate is `blocked` and math resolved counterexample-search gate is `passed`.

### PF-REAL-016 — Copy installer includes private worknotes in installed plugin

- status: Closed in source and installed copy; clean-round count reset after this fix.
- discovered_at: 2026-07-04T07:47:32+08:00 while processing wave2 installed packaging audit.
- real trigger: `wave2_installed_packaging_audit.md` observed installed copy includes `worknotes/`.
- observed failure: `/home/xu/.hermes/plugins/ponder_forge` carries source worknotes/real-run artifacts that are not needed for runtime plugin operation.
- impact: installed plugin can be bloated and can leak stale/private agent evidence into a runtime plugin directory; future install comparisons become noisier.
- root cause: `scripts/copy_install_smoke.py` excludes `reference`, `tmp`, caches, and coverage files but not `worknotes`.
- required fix boundary: exclude `worknotes` from copied installs; keep source worknotes in the repo and keep runtime skills/prompts/tests/scripts installed.
- fix: added `worknotes` to `EXCLUDED_DIR_NAMES`; `test_copy_install_smoke.py` asserts copied targets omit `worknotes/`.
- verification: focused source suite `30 passed`; full source suite `46 passed`; installed-copy suite `46 passed`; installed compileall exit 0; installed smoke confirmed `installed_worknotes=false`, no direct-tool string leakage in delegation, and JSON error envelope still works.
