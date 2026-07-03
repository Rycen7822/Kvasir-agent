# PF-REAL-010..015 Design Audit

## Existing owner seams

- CLI envelope: `cli.py` owns parser construction, JSON success/error envelope, command dispatch.
- Reconcile: `reconcile.py` owns stale/orphan retry behavior.
- Status: `cli.py::cmd_status` owns compact next-action reporting.
- Profile gate policy: `profiles.py` declares vocabulary/groups; `gates.py` evaluates support and profile-specific gaps.
- Delegation child context: `delegation.py` owns first-wave child prompts; `reconcile.py` currently duplicates a thinner retry prompt.

## Design decisions

- D1: Fix argparse errors by subclassing `argparse.ArgumentParser.error()` to raise `ValueError`. This preserves normal `--help` and lets `main()` emit JSON for validation failures.
- D2: Validate `run_id` at `reconcile_run()` start. This keeps behavior consistent with other run-scoped commands and avoids CLI-specific checks.
- D3: Have `cmd_status()` inspect persisted run completion before deriving next action. Return an explicit terminal action instead of another finalize request.
- D4: Make analysis metric evidence require `command` and successful `exit_code` on the same item. This aligns gate enforcement with child guidance.
- D5: Generate report contract examples from `ProfileSpec`: critical assertion type and required evidence groups. Use profile-specific preferred examples only where group alternatives need a safer default.
- D6: Export/reuse the child-context builder from `delegation.py` for reconcile retry payloads instead of duplicating a thin prompt.
- D7: Patch only clear profile-gate contract mismatches: coding needs successful execution proof; math advertises `proof_check`; math only blocks positive/unresolved counterexample evidence.
- D8: Add `gap_type="missing_profile_evidence"` to profile-evidence gaps for operator diagnostics.

## Compression / no-overdesign checks

- No new CLI command is needed for this repair.
- No database migration is needed.
- No plugin tools/hooks are added.
- No broad policy hardening for design/research artifact coverage is included; those are documented as remaining policy boundaries unless later real runs prove them blocking.
- Tests should be focused on the confirmed reproductions and existing lifecycle behavior.
