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
