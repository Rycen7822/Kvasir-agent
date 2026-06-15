# Parent Controller Reference

Use this reference only for the parent/main agent that orchestrates an Idea-Spark toolset-first room.

## Parent responsibilities

The parent creates the room, seeds initial artifacts, launches bounded `delegate_task` children, verifies each phase, re-reads the main skill after every phase, retries missing phase-critical roles when appropriate, records or delegates the terminal gate, exports the ledger, and writes the standalone handoff report.

The parent must keep the phase loop moving. `r1`, `r2`, and `r3` are progress states, not completion states.

## Round-continuity rule

Do not stop after `r1`, `r2`, or `r3`. These phases are progress checkpoints only; the parent continues after verification and the mandatory skill re-read checkpoint until `r4 / Gate` records a real terminal gate.

Canonical phase aliases: `r0/seed` = `Seed / Framing`; `r1/review` = `r1 / Novelty Attack`; `r2/rebuttal` = `r2 / Author Rebuttal / Improvement Draft`; `r3/re-review` = `r3 / Re-review / Cross-examination`; `r4/gate` = `r4 / Gate`; `final/handoff` = ledger export plus standalone handoff report.

## Continuous r1 → r2 → r3 → r4 loop

1. `r0 / seed`: create the room with `idea_spark_room_create` and seed `ResearchGoal`, `IdeaCard`, and `EvaluationRubric`.
2. `r1 / review`: launch independent reviewers with `toolsets=["idea_spark", "skills"]` by default. Expected outputs include `PriorArtEvidence`, `NoveltyObjection`, `FeasibilityObjection`, `ReviewerRisk`, `BenchmarkRequirement`, `StressTest`, or `ExperimentPlan`.
3. Verify r1: read status/messages/artifacts. If a required reviewer joined but wrote no artifact, relaunch that role once with a narrower prompt or record the missing evidence as an `OpenNeed`.
4. Re-read `skill_view(name="idea-spark:idea-spark-usage")`, confirm r1 is not terminal, then launch r2.
5. `r2 / rebuttal-repair`: launch `AuthorAdvocate`, `SchemaSurgeon`, `ExperimentPlanner`, `BaselineRepair`, or analogous repair roles. Expected outputs include `Rebuttal`, `RevisionPlan`, `ExperimentPlan`, `BenchmarkRequirement`, and `RegimeTransition` linked to r1 objections.
6. Verify r2, retry missing required repair roles once when they joined but wrote no artifacts, then re-read the main skill before r3.
7. `r3 / re-review`: launch prior-art re-review, feasibility re-review, skeptical AC, and open-need curator roles. Expected outputs include `MetaReview`, `ScoreCard`, and `OpenNeed` creation/update.
8. Verify r3, re-read the main skill, then launch r4.
9. `r4 / gate`: Gatekeeper reads the full ledger, writes final `ScoreCard` and `MetaReview`, and calls `idea_spark_gate_record(close_room=true)`. Gatekeeper must call `idea_spark_gate_record`; a message-only gate is not final.
10. Verify terminal state with `idea_spark_room_status`. Stop only when `has_terminal_gate=true`.
11. Export the ledger and, when the result is for a human reader, write the standalone handoff report using `references/handoff-report.md`.

## Mandatory skill re-read after each phase

Because Idea-Spark rooms can produce long context, the parent must refresh the workflow contract after every long delegate round.

Required checkpoint after r1, r2, r3, and before final report:

```text
1. Read room status/messages/artifacts for the just-completed phase.
2. Call skill_view(name="idea-spark:idea-spark-usage").
3. Confirm which phase is next by applying the main skill's checklist.
4. Launch the next phase immediately unless a real blocker requires user input or an OpenNeed.
```

This checkpoint prevents the common failure mode where the parent reports r1 results as final or forgets to write the handoff report after gate.

## Phase verification checklist

- r1 verification: at least one narrative message and typed artifact per substantive reviewer; objections/risks/evidence are linked or named clearly enough for r2 to answer them.
- r2 verification: rebuttal/repair artifacts explicitly answer r1 objections; baseline and experiment repair are durable artifacts, not only messages.
- r3 verification: re-review artifacts state which r2 repairs are resolved, partially resolved, or unresolved; open needs are created or updated for acceptance blockers.
- r4 verification: final `ScoreCard` and `MetaReview` exist; `idea_spark_gate_record(close_room=true)` has been called; `idea_spark_room_status` reports `has_terminal_gate=true`.

## Retry and timeout policy

Use finite waits. If a role times out or returns without writing artifacts, inspect the room state instead of trusting the child summary. Retry a phase-critical missing role once with a narrower prompt that reads existing room artifacts rather than rereading all source material. If the retry still fails, record the missing contribution as an `OpenNeed` and continue to the next phase when the gate can still produce `needs_more_evidence`.

## Parent prompt skeleton

```text
You are the parent/orchestrator for room <ROOM_ID>. Load idea-spark:idea-spark-usage. For this phase, launch bounded delegate_task children with toolsets=["idea_spark", "skills"] by default. Add external toolsets only for evidence/file access that the role needs. After children return, verify room status/messages/artifacts, re-read idea-spark:idea-spark-usage, and continue to the next phase. Do not stop after r1/r2/r3. Only stop after a real gate_record close_room=true and has_terminal_gate=true.
```
