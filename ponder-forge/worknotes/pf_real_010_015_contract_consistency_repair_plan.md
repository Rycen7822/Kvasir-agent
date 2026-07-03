# PF-REAL-010..015 Contract Consistency Repair Plan

> **For Hermes:** Implement directly with small TDD patches, then reinstall and restart clean rounds.

**Goal:** Close the wave2-confirmed CLI/profile/gate/delegation contract defects before claiming Ponder-Forge stability.

**Architecture:** Patch existing owner seams only: `cli.py` for JSON envelope/status, `reconcile.py` for run validation/retry context, `gates.py` and `profiles.py` for profile evidence semantics, `delegation.py` for profile-derived child report contracts. No new Hermes tools/hooks or database migration.

**Design audit:** `worknotes/tmp_pf_real_010_015_contract_consistency/01_design_audit.md`.

**Tech Stack:** Python stdlib, pytest, installed CLI temp-home smokes.

---

## Task 1 — CLI error envelope and status terminal action

- Add tests proving missing required CLI args emit JSON and completed runs report terminal next action.
- Implement `JsonArgumentParser.error()` and update `cmd_status()` to inspect completed/final run state.
- Verify focused CLI tests.

## Task 2 — Reconcile unknown-run validation and retry context reuse

- Add tests proving unknown reconcile fails and orphan retry payload includes the same schema/profile guidance as first-wave delegations.
- Export/reuse a delegation child-context builder from `delegation.py`.
- Validate run existence at `reconcile_run()` entry.
- Verify focused reconcile/delegation tests.

## Task 3 — Analysis/coding/math gate contract alignment

- Add RED tests:
  - analysis `metric_output.exit_code=1` blocks;
  - coding `root_cause_trace + failing_test(exit_code=1)` blocks;
  - coding with successful execution proof passes;
  - math `proof_check` is advertised and passes;
  - math resolved/negative counterexample-search evidence does not block, but positive/unresolved counterexample evidence still blocks;
  - missing profile evidence gaps include `gap_type`.
- Implement minimal gate/profile changes.
- Verify focused gate/profile tests.

## Task 4 — Profile-derived delegation contracts

- Add tests proving coding delegations include `code_claim`, coding evidence examples, and no placeholder or analysis evidence leakage.
- Ensure analysis contract still includes `data_result`, `metric_output`, `command`, and successful `exit_code` guidance.
- Verify focused prepare-delegations tests.

## Task 5 — Landing verification and install

- Run full source tests and `compileall`.
- Reinstall with `scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge`.
- Run installed-copy tests and `compileall`.
- Run installed temp-home reproductions proving PF-REAL-010..015 closed.
- Update `problems.md` and `note.md`.

## Task 6 — Restart clean rounds

- Run at least three fresh installed real-task rounds after the last fix.
- Each round must exercise `start`, `plan`, `delegations`, `submit-report`, `verify`, `gate`, `finalize`, `status`, `reconcile`, late-submit rejection, and quest guard.
- Stop only after three consecutive rounds have no new plugin issue and all pending worker reports have been handled.
