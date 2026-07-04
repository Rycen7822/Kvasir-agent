# PF-REAL-023 Reconcile Gate Gaps Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** When a real Ponder-Forge run is blocked by gate gaps after independent review, `reconcile` must return executable repair payloads instead of an empty success response.

**Architecture:** Keep the fix in existing owner seams: `verifier.py` records non-accept verdicts as assertion states, `gates.py` gates only active assertions, and `reconcile.py` creates queued gate-gap repair tasks from current gate gaps. No schema migration, new command, cache, or external adapter.

**Design audit:** This document is the design artifact and implementation plan. The change rewrites too-narrow existing behavior rather than appending a parallel controller helper.

**Tech Stack:** Python stdlib, SQLite-backed `PonderForgeStore`, pytest.

---

## Sources inspected

- `reconcile.py:17-72` — currently handles stale/orphan tasks only and returns `{tasks: []}` for blocked gate gaps.
- `gates.py:131-226` — currently evaluates every critical assertion regardless of assertion status.
- `verifier.py:86-125` — currently marks accept assertions accepted, but leaves revise/reject targets active and unmodified.
- `cli.py:219-293` — `status` picks `delegations` only when queued tasks exist; otherwise blocked gate goes to `verify`.
- `tests/test_hooks_reconcile.py:32-102` and `tests/test_gates_profiles.py:155-214` — current gate/reconcile coverage.
- Real run evidence: `pf_run_80cb097d3870` recorded 83 reviewer verdicts; `gate` blocked; `reconcile` returned `payload_tasks=0`.

## Design iteration log

### Iteration 1 — Root cause and owner seam

1. Why did real reconcile fail to advance? `reconcile_run` only inspects stale `running` tasks and orphan retries; it never reads gate gaps.
2. Is this a controller-script problem? No. The installed CLI returned success with no payload, so the agent-facing workflow seam is `reconcile.py`.

Research added: `reconcile.py`, live `26_reconcile_after_blocked_gate.json`.
Design change: add D1 gate-gap repair tasks in `reconcile.py`.
Remaining uncertainty: how to let repaired assertions converge without old rejected/revise assertions permanently blocking.

### Iteration 2 — Convergence semantics

1. What currently happens to revise/reject verdicts? `record_independent_verdict` stores the verdict and finishes the reviewer task, but only `accept` updates assertion status.
2. How can repairs converge without migration? Reuse `assertions.status`: `revise` -> `needs_revision`, `reject` -> `rejected`; gate excludes non-active statuses and waits for a queued repair task/new assertion.

Research added: `verifier.py`, `gates.py`, `store.py`, `cli.py` status behavior.
Design change: add D2/D3 below.
Remaining uncertainty: whether queued repair tasks can be bypassed by direct `finalize`.

### Iteration 3 — Installed false-green guard

1. What did installed live smoke show after D1-D3? `reconcile` created 63 repair tasks and `status.next_required_action=delegations`, but `gate_status` became `passed` because old revised assertions were inactive and remaining active assertions were accepted.
2. Can direct `finalize` bypass queued repairs? Yes unless `evaluate_gate` itself blocks unfinished `gate_gap_repairer` tasks.

Research added: installed outputs `27_reconcile_after_pf_real_023.json`, `28_status_after_pf_real_023_reconcile.json`, and direct `gate/finalize` smoke after reinstall.
Design change: add D4/C4: gate blocks unfinished gate-gap repair tasks until their reports are submitted/finished.
Remaining uncertainty: none for PF-REAL-023; repair-agent content quality remains part of the continuing live workflow.

## Baseline design inventory

| id | existing element | current assumption/contract | evidence | owner/seam | risk if changed |
|---|---|---|---|---|---|
| B1 | `reconcile_run` | Reconcile means stale/orphan task recovery only. | `reconcile.py:17-40` | `reconcile.py` | Expanding scope could create duplicate work if not deduped. |
| B2 | Gate critical set | Every critical assertion blocks forever until supported + accepted, regardless of revision status. | `gates.py:141-191` | `gates.py` | Excluding too much could allow false finalization. |
| B3 | Verdict state | Only accept changes assertion status; revise/reject leave target active. | `verifier.py:123-125` | `verifier.py` | Changing status must preserve audit trail and not delete evidence. |
| B4 | CLI status routing | Queued tasks drive `next_required_action=delegations`; otherwise blocked gate drives `verify`. | `cli.py:232-240` | `cli.py` | Repair tasks must be real queued tasks, not only prose. |

## Proposed design ledger

| id | baseline refs | proposed decision | intent | files/seams touched | expected impact | rollback/proof |
|---|---|---|---|---|---|---|
| D1 | B1, B4 | `reconcile_run` evaluates current gate, creates/dedupes queued `gate_gap_repairer` tasks for assertion-targeted gaps, and returns native `delegate_task_payload_suggestion`. | Turn blocked gates into executable next work. | `reconcile.py`, `tests/test_hooks_reconcile.py` | Real blocked runs can advance by delegated repair reports. | Focused pytest asserts repair task payload and dedupe. |
| D2 | B2 | Gate ignores assertions whose status is `needs_revision`, `rejected`, or `superseded`; accepted/unverified remain active. | Let repaired/new assertions replace failed targets without deleting audit history. | `gates.py`, `tests/test_gates_profiles.py` | Old revise/reject targets stop permanently blocking; missing active critical assertions still block. | Focused pytest: revised assertion alone blocks as missing critical, not passes. |
| D3 | B3 | Recording `revise` marks target `needs_revision`; recording `reject` marks target `rejected`; `accept` unchanged. | Make reviewer verdicts affect active gate state. | `verifier.py`, `tests/test_verifier_independence.py` | Gate/reconcile has durable state to act on. | Focused pytest on record verdict statuses. |
| D4 | B2, B4 | `evaluate_gate` adds `incomplete_gate_gap_repairs` while queued/running/orphan gate-gap repair tasks exist. | Prevent direct `finalize` from bypassing repairs after reconcile makes failed assertions inactive. | `gates.py`, `tests/test_hooks_reconcile.py` | Installed status and finalize remain blocked until repair reports finish. | Focused pytest plus installed gate/status/finalize smoke on `pf_run_80cb097d3870`. |

## Compression review

| id | baseline refs | decision refs | compression action | why this is not append-only | code-size pressure | proof or deferral owner |
|---|---|---|---|---|---|---|
| C1 | B1 | D1 | rewrite | Improves the owning `reconcile` command instead of adding a separate collector/controller workaround. | neutral/add small helper functions only | `tests/test_hooks_reconcile.py` |
| C2 | B2 | D2 | rewrite | Changes existing active-gate definition rather than adding a second gate mode. | small helper | `tests/test_gates_profiles.py` |
| C3 | B3 | D3 | rewrite | Reuses existing assertion status field; no schema or status table. | minimal | `tests/test_verifier_independence.py` |
| C4 | B2, B4 | D4 | rewrite | Keeps finalization safety in the existing gate rather than duplicating queued-task checks in `finalize`. | small helper | `tests/test_hooks_reconcile.py` + installed smoke |

## Implementation plan

### Task 1: RED test for reconcile gate-gap repair payload

- Modify `tests/test_hooks_reconcile.py`.
- Add a blocked analysis run with a critical assertion lacking `metric_output.command`/`exit_code=0`.
- Expected RED: current `reconcile_run` returns no `gate_status`, no repair task, and no queued `gate_gap_repairer`.

### Task 2: Implement reconcile gap tasks

- Modify `reconcile.py`.
- Import `evaluate_gate`.
- Create/dedupe queued `gate_gap_repairer` tasks from assertion-targeted gaps.
- Include exact JSON output contract (`submit-report` payload with `run_id`, repair task `task_id`, `assertions`, `evidence`, and `"artifacts": []`).
- Mark target assertions `needs_revision` when a repair task is created.

### Task 3: RED/GREEN for verifier non-accept status and gate active filtering

- Modify `tests/test_verifier_independence.py` and `tests/test_gates_profiles.py`.
- Add coverage that revise/reject updates assertion status.
- Add coverage that `needs_revision`/`rejected` assertions are not treated as active gate blockers, while an empty active critical set still blocks.

### Task 4: Implement verifier/gate status semantics

- Modify `verifier.py` and `gates.py`.
- Keep `accept` behavior unchanged.
- Add `_active_for_gate` helper in `gates.py` and use it in `evaluate_gate` and `supported_critical_assertion_ids`.

### Task 4.5: Guard against finalize false-green with unfinished repair tasks

- Modify `tests/test_hooks_reconcile.py` and `gates.py`.
- Add RED coverage for the installed-smoke failure mode: one supported active assertion plus one reconciled failed assertion must still block while the repair task is queued.
- Add `incomplete_gate_gap_repairs` gate gaps for unfinished `gate_gap_repairer` tasks.

### Task 5: Verify, install, and live smoke

- Run focused pytest for changed tests.
- Run broader pytest suite.
- Copy/install plugin to `/home/xu/.hermes/plugins/ponder_forge` using existing install workflow.
- Re-run installed CLI `reconcile` on `pf_run_80cb097d3870` with isolated `HERMES_HOME` and confirm queued repair payloads are emitted and status routes to `delegations`.
- Do not modify `/home/xu/project/loop/DeepScientist/quests/001`.

## Proof plan and false-green risks

- Targeted RED/GREEN: `pytest tests/test_hooks_reconcile.py::test_reconcile_creates_gate_gap_repair_tasks -q` must fail before implementation and pass after.
- Gate semantic proof: revised/rejected assertions cannot silently pass; no active critical assertion still blocks.
- Live installed proof: the actual blocked run must produce non-empty repair tasks via installed CLI, not only source tests.
- False green risk: a repair payload without a recoverable repair task id cannot be submitted; tests assert the native payload remains `goal/context/role` only and carries the repair task id in the marker/context.
- False green risk found by installed smoke: making failed assertions inactive can make `gate` pass before repair tasks finish; regression and installed smoke assert `incomplete_gate_gap_repairs` blocks `finalize`.

## Blast radius and rollback

- Touched code is limited to `reconcile.py`, `gates.py`, `verifier.py`, and tests.
- No database migration or quest mutation.
- Rollback is a normal git revert of this commit; existing audit rows remain valid because status values are plain text in an existing column.

## Open questions / deferrals

- This slice does not auto-rewrite Stage10 claims; it only gives Ponder-Forge an executable repair loop. The real quest remains read-only.
- This slice does not collapse multiple gaps on the same assertion into a single human-friendly narrative beyond context grouping; repair agents can submit a new refined report/assertion.
