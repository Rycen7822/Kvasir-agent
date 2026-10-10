# Parent Controller Reference

Use this reference only for the parent/main agent that orchestrates an Idea-Spark room.

## Parent responsibilities

The parent creates the room, seeds initial artifacts, launches bounded native children, verifies each phase, re-reads the main skill after every phase, retries missing phase-critical roles when appropriate, reviews and records the terminal gate, exports the ledger, and writes the standalone handoff report. Use the selected host's actual agent interface; Hermes uses `delegate_task`, while Codex uses its native agent tools.

The parent must keep the phase loop moving. `r1`, `r2`, and `r3` are progress states, not completion states.

## Round-continuity rule

Do not stop after `r1`, `r2`, or `r3`. These phases are progress checkpoints only; the parent continues after verification and the mandatory skill re-read checkpoint until `r4 / Gate` records a real terminal gate.

Canonical phase aliases: `r0/seed` = `Seed / Framing`; `r1/review` = `r1 / Novelty Attack`; `r2/rebuttal` = `r2 / Author Rebuttal / Improvement Draft`; `r3/re-review` = `r3 / Re-review / Cross-examination`; `r4/gate` = `r4 / Gate`; `final/handoff` = ledger export plus standalone handoff report.

Do not send a user-facing final answer after r1, r2, or r3. A parent-side synthesis, an exported ledger, or a child summary after these phases is only a checkpoint; immediately continue to the next phase unless a real blocker requires user input or an OpenNeed.

## Current-workdir phase ledger

Before launching the first child phase, create or update `.work/idea_spark_phase_ledger.md` in the project, unless the user explicitly names another durable project path. Do not rely on memory, context compaction summaries, or `session_search` to reconstruct the active phase later; active live sessions may not be indexed yet.

At minimum, the phase ledger must record: room id or room label, current phase, next phase, expected agents for the current phase, verification counts, last room-status check, last installed-skill re-read checkpoint, open blockers, and final handoff report path.

After verifying each phase, append a stage checkpoint marker such as `r1_verified_next=r2`, `r2_verified_next=r3`, `r3_verified_next=r4`, or `r4_gate_verified_next=final/handoff`. If the parent is about to tell the user progress, the latest checkpoint marker must say which phase is verified and which phase starts next.

## Continuous r1 → r2 → r3 → r4 loop

1. `r0 / seed`: create the room and seed `ResearchGoal`, `IdeaCard`, and `EvaluationRubric`.
2. `r1 / review`: launch independent reviewers. Expected outputs include `PriorArtEvidence`, `NoveltyObjection`, `FeasibilityObjection`, `ReviewerRisk`, `BenchmarkRequirement`, `StressTest`, or `ExperimentPlan`.
3. Verify r1: read status/messages/artifacts. Collect each prepared receipt after native completion and read the full files. Repair missing registration from the existing file or full native reply before considering any research retry.
4. Re-read the installed SKILL.md, confirm r1 is not terminal, then launch r2.
5. `r2 / rebuttal-repair`: launch `AuthorAdvocate`, `SchemaSurgeon`, `ExperimentPlanner`, `BaselineRepair`, or analogous repair roles. Expected outputs include `Rebuttal`, `RevisionPlan`, `ExperimentPlan`, `BenchmarkRequirement`, and `RegimeTransition` linked to r1 objections.
6. Verify r2, recover missing registration from delivered files or complete native replies, then re-read the main skill before r3.
7. `r3 / re-review`: launch prior-art re-review, feasibility re-review, skeptical AC, and open-need curator roles. Expected outputs include `MetaReview`, `ScoreCard`, and `OpenNeed` creation/update.
8. Verify r3, re-read the main skill, then launch r4.
9. `r4 / gate`: Gatekeeper reads the full ledger and referenced files, then delivers its proposed final scores and review. The parent records `ScoreCard` / `MetaReview` as needed; the parent calls `idea_spark_gate_record` with `close_room=true`; a message-only gate is not final.
10. Verify terminal state with `idea_spark_room_status`. Stop only when `has_terminal_gate=true`.
11. Export the ledger and, when the result is for a human reader, write the standalone handoff report using `references/handoff-report.md`.

## Mandatory skill re-read after each phase

Because Idea-Spark rooms can produce long context, the parent must refresh the workflow contract after every long delegate round.

Required checkpoint after r1, r2, r3, and before final report:

```text
1. Read room status/messages/artifacts for the just-completed phase.
2. Collect prepared receipts and verify every phase-critical role delivered a complete, readable file.
3. Update .work/idea_spark_phase_ledger.md in the project with the stage checkpoint marker, counts, blockers, and next phase.
4. Re-read the installed SKILL.md with the native file tools (Hermes may use skill_view).
5. Confirm which phase is next by applying the main skill's checklist.
6. Launch the next phase immediately unless a real blocker requires user input or an OpenNeed.
```

This checkpoint prevents the common failure mode where the parent reports r1 results as final or forgets to write the handoff report after gate.

## Phase verification checklist

- r1 verification: a registered complete file artifact per substantive reviewer; objections/risks/evidence are linked or named clearly enough for r2 to answer them.
- r2 verification: rebuttal/repair artifacts explicitly answer r1 objections; baseline and experiment repair are durable artifacts, not only messages.
- r3 verification: re-review artifacts state which r2 repairs are resolved, partially resolved, or unresolved; open needs are created or updated for acceptance blockers.
- r4 verification: final `ScoreCard` and `MetaReview` exist; `idea_spark_gate_record(close_room=true)` has been called; `idea_spark_room_status` reports `has_terminal_gate=true`.
- final/handoff verification: deterministic ledger export exists for audit only; standalone handoff report exists in the current working directory, not only under `/tmp`; the handoff is detailed enough for a researcher who cannot see the room, repository, dashboard, PDFs, or prior chat.

## Retry and timeout policy

Use finite native waits. A file appearing on disk does not mean its worker has finished: collect after the host reports completion or interruption, and inspect partial output before registering it. A ledger failure is a delivery retry, not a reason to repeat research. Repeat `files collect` with the same receipt; it retains the artifact ID and existing review status. For a file write failure, save the full native final reply to the assigned file and collect it. If neither a usable file nor a complete reply exists, retry a phase-critical role once with a narrower prompt or record an `OpenNeed`. A new research assignment or revision gets a new receipt and file; do not overwrite an already delivered result.

## File preparation and parent collection

`idea-spark` below abbreviates the absolute shared CLI prefix described in `HOSTS.md`.

```sh
idea-spark files prepare --room-id ROOM --agent-id prior-art-r1 --role PriorArtBreaker --round-id r1 --phase review --type PriorArtEvidence --title "Prior art review"
```

Save the returned `receipt_path`, `artifact_id` and `file_path` in the phase ledger. Give the worker the output path and a separate `.work/delphi/<artifact_id>/` scratch directory. Receipts and outputs live beside the selected database under `deliveries/<artifact_id>/`; they are durable project state, not scratch files.

After native workers settle, batch-register their files:

```sh
idea-spark files collect /absolute/receipt-a.json /absolute/receipt-b.json
```

Each receipt reports its own success/error; completed entries remain saved if another file is missing. Retrying the batch does not duplicate them. A receipt is bound to its original database/project. `idea_spark_artifact_read` returns the absolute `file_path`; use native file tools to read the complete body. The room export also contains the paths and the dashboard loads the file on expansion. The database stores summary and identity, not a second full copy. Files must remain available to later readers.

The collector registers the producer as a participant in the same artifact transaction. Parent-owned `idea_spark_artifact_link`, `idea_spark_need_create` / `idea_spark_need_update`, optional `idea_spark_message_post` and `idea_spark_gate_record` preserve research structure and decisions. Collection itself does not accept claims or close the room.

## Parent prompt skeleton

```text
You are the parent/orchestrator for room <ROOM_ID>. Read the installed Idea-Spark skill and native host contract. Prepare one durable output path per assignment. Give each native worker the absolute CLI/state paths, relevant input files, output path and its own .work scratch directory. After native completion, collect the receipts, read complete files and verify room status/artifacts, re-read the skill, and continue to the next phase. Do not stop after r1/r2/r3. Only stop after a real gate_record close_room=true and has_terminal_gate=true.

Maintain .work/idea_spark_phase_ledger.md in the project. Each checkpoint must say current_phase, verified counts, next_phase, latest skill reread, open blockers, and final handoff path. Do not send a final answer until final/handoff is complete.
```
