# PF-REAL-021 Live Subagent Stability Closure Plan

> **Planning status:** COMPLETE after self-review.
>
> **Confidence:** 100% confidence in this plan as the next execution plan. This confidence covers the plan's clarity, boundaries, and ability to drive the stability loop. It does not pre-claim that Ponder-Forge is stable until the live rounds actually pass.

**Goal:** Close the remaining proof gap by running Ponder-Forge through real Stage10 tasks with actual Hermes live subagents, not controller-generated substitute reports.

**Architecture:** Keep Ponder-Forge's existing CLI/state architecture. Use the installed plugin CLI to create real runs and produce delegation payloads. The controller dispatches those exact payloads through `delegate_task`, stores each returned JSON report outside the quest path, submits accepted reports with the CLI, then dispatches verifier subagents from the generated reviewer payloads. Any real failure becomes a PF-REAL issue with a small patch, reinstall, and rerun.

**Design audit:** No code design change is planned before a reproduced failure. The existing owning seams are `delegation.py` for agent-facing context, `report_ingest.py` for report acceptance, `verifier.py` for reviewer context/verdicts, and `cli.py` for public command/error contracts. This plan deliberately avoids adding wrappers, alternate schemas, or fake subagent simulators.

**Tech Stack:** Python stdlib CLI, SQLite state under isolated `HERMES_HOME`, Hermes `delegate_task`, Ponder-Forge installed copy at `/home/xu/.hermes/plugins/ponder_forge`.

---

## Non-Negotiable Boundaries

- Real task path: `/home/xu/project/loop/DeepScientist/quests/001`.
- Quest path is read-only. Do not write, patch, format, clean, or delete anything under the quest path.
- Source edits are limited to `/home/xu/project/autosci-delphi/ponder-forge`.
- Installed copy is `/home/xu/.hermes/plugins/ponder_forge`, copied install, not symlink.
- Do not edit Hermes core or `idea-spark`.
- Keep patches small and only after a reproduced real issue.
- Commit and push after each fix/proof update.
- Do not use unit tests as the final stability proof.
- Do not report final completion while any dispatched live subagent result is pending.

## Acceptance Gates

A live round counts as clean only if every item below is true:

1. Installed plugin copy is enabled and source/installed key hashes match before the round.
2. Quest baseline signature is captured before and after; signatures are equal.
3. Ponder-Forge CLI sequence uses the installed copy: `start -> plan -> delegations`.
4. The controller dispatches the exact `delegate_task_payload.tasks` from `delegations` as orchestrator subagents for lane coordinators.
5. Each lane coordinator returns a parseable JSON report with:
   - matching `run_id`, `task_id`, and `role`;
   - all assigned child reports;
   - required evidence groups for the profile;
   - top-level `artifacts` as a JSON array.
6. Reports are submitted through installed `submit-report`, not inserted manually into the database.
7. `status` after reports routes to `verify` and shows complete swarm topology.
8. `verify --mode independent_review` creates reviewer payloads with rich assertion/evidence/artifact context and one profile marker.
9. The controller dispatches reviewer payloads to actual leaf subagents or records a new PF-REAL issue if the volume/runtime cannot complete; accepted verdicts must be based on returned reviewer JSON/rationale, not blind controller acceptance.
10. Gate passes only after independent verdicts are recorded.
11. `finalize`, `reconcile`, final `status`, and late-submit rejection all pass.
12. No new plugin issue appears during the round.

Three consecutive clean live rounds are required after the last fix. A controller-generated report round cannot count toward this live streak.

## Execution Tasks

### Task 1: Start a fresh live-subagent run

**Objective:** Create one isolated installed-copy Ponder-Forge run for the real Stage10 task.

**Files:**
- Write artifacts under `worknotes/real_subagent_stability_2026-07-04/live_round_XX/`.
- Do not write under the quest path.

**Steps:**
1. Capture quest signature before the run.
2. Set `HERMES_HOME` to a round-specific directory under `worknotes/real_subagent_stability_2026-07-04/hermes_home_live_XX`.
3. Run installed CLI `start --goal <real task> --profile analysis`.
4. Run installed CLI `plan --run-id <run_id>`.
5. Run installed CLI `delegations --run-id <run_id>`.
6. Save all JSON outputs under the round worknote directory.

**Proof:** `delegations` returns exactly eight lane coordinator orchestrator tasks for the default 8x4 run.

### Task 2: Dispatch live lane coordinator subagents

**Objective:** Exercise Ponder-Forge's generated lane coordinator instructions with actual Hermes orchestrator subagents.

**Files:**
- Save raw returned summaries under the round worknote directory.

**Steps:**
1. Dispatch the eight lane coordinator payload tasks exactly from the `delegations` output.
2. Use `role="orchestrator"` for lane coordinator tasks.
3. Preserve each task's generated `goal` and `context`.
4. Require each subagent to return one JSON object only.
5. Wait for async results; do not claim completion while pending.

**Proof:** Every lane result is parseable JSON and satisfies the lane report contract.

### Task 3: Submit returned live lane reports

**Objective:** Exercise installed `submit-report` using live subagent outputs.

**Steps:**
1. For each returned report, validate shape in the controller before submission.
2. Submit through installed CLI only.
3. Run `status` and inspect `swarm.finished_lane_count`, `finished_child_count`, `incomplete_task_count`, and `next_required_action`.

**Proof:** `status.next_required_action == "verify"` and swarm topology is complete.

### Task 4: Dispatch live reviewer subagents

**Objective:** Exercise `verify` generated independent reviewer payloads with actual Hermes leaf subagents.

**Steps:**
1. Run `verify --mode independent_review` for critical assertions.
2. Save reviewer payloads.
3. Dispatch reviewer payload tasks as `role="leaf"`.
4. Require each reviewer to return parseable JSON with verdict, confidence, rationale, and target id.
5. Record verdicts through installed CLI only.

**Proof:** `status` after verdicts routes to `finalize`, and reviewer tasks are not left queued.

### Task 5: Finalize, reconcile, and classify the round

**Objective:** Complete the full Ponder-Forge lifecycle.

**Steps:**
1. Run `gate` and require `passed`.
2. Run `finalize` and require final output.
3. Run `reconcile` and require empty repair/orphan suggestions.
4. Run final `status` and require `run_status=completed`, `next_required_action=complete`.
5. Try a late submit and require rejection.
6. Capture quest signature after the run and compare with before.
7. Write a round summary and update `note.md`.

**Proof:** The round is clean only if all acceptance gates pass and no new PF-REAL issue is opened.

### Task 6: If a real issue appears, run the repair loop

**Objective:** Keep the stability loop honest.

**Steps:**
1. Immediately record the issue in `problems.md` and `note.md` with trigger, root cause hypothesis, and impact.
2. Stop only if severe blocking; otherwise continue collecting evidence.
3. Write a focused repair plan under `worknotes/` using this same evidence-backed planning discipline.
4. Patch the owning seam only; no overdesign and no unrelated refactor.
5. Run focused tests, source full tests, copy install smoke, installed tests, and a real installed repro.
6. Commit and push.
7. Restart the three-clean-live-round streak from zero.

## Current Confidence Review

- The plan does not rely on controller-generated substitute reports for clean rounds.
- The plan preserves the quest read-only boundary.
- The plan names exact lifecycle gates and failure classification points.
- The plan has no new abstraction, schema, compatibility mode, or daemon.
- The plan leaves code untouched until a live reproduced issue requires a small patch.
- The remaining uncertainty is execution outcome, not planning ambiguity.

## Completion Statement

This plan is complete and is the active execution plan for PF-REAL-021. The implementation/stability goal is not complete until live subagent rounds pass under this plan.
