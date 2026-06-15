---
name: idea-spark-usage
description: Thin workflow router for Idea-Spark shared-ledger review rooms: parent-orchestrated r1-r4 discussion-until-gate, subagent role contracts, CLI-first operation, and standalone handoff reports.
version: 0.2.6
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [idea-spark, delegate_task, multi-agent, research-review, hermes-plugin]
---

# Idea-Spark Usage

Load this when the task asks to run, coordinate, inspect, or explain an Idea-Spark review room.

Idea-Spark is a Hermes standalone plugin named `idea-spark`. It is not a subagent launcher: the **parent agent** launches bounded `delegate_task` children, and Idea-Spark supplies the shared SQLite ledger where those children join, read, write messages, write typed artifacts, record open needs, and record gates.

Default mode is **skill + CLI**. Use `hermes idea-spark call ... --json-file ...` unless explicit tool-mode has been enabled and the Hermes session was reset.

## Who is this document for?

- **[PARENT-ONLY] Parent/main agent:** read this whole thin workflow first. If orchestrating a room, also load `references/parent-controller.md`.
- **[SUBAGENT-ONLY] Subagent/child agent:** load this skill, then load `references/subagent-contract.md`. Follow subagent-only rules unless explicitly assigned orchestration duties.
- **Human-readable reporting:** after the terminal gate, load `references/handoff-report.md` before writing a report for researchers outside the room.
- **CLI/dashboard mechanics:** load `references/cli-dashboard.md` only when you need exact commands, tool-mode configuration, dashboard checks, or artifact/type reference.

## Role routing — choose exactly one lane first

| If this run is... | You are... | Read next | Do not do |
|---|---|---|---|
| Creating/controlling the room, launching delegates, moving r1→r2→r3→r4, closing gate, or writing final report | **[PARENT-ONLY] parent/main agent** | `references/parent-controller.md` | Do not behave like a one-role reviewer or stop after a child summary. |
| A delegated reviewer/rebutter/planner/gatekeeper | **[SUBAGENT-ONLY] subagent/child agent** | `references/subagent-contract.md` | Do not launch agents, manage the room, export reports, or load parent-only workflow unless told. |
| Writing a researcher-facing deliverable after the room is gated | **[PARENT-ONLY] report writer** | `references/handoff-report.md` | Do not hand off the raw ledger as the readable report. |
| Looking up exact CLI, dashboard, tool-mode, type, or command syntax | **mechanics lookup** | `references/cli-dashboard.md` | Do not copy CLI mechanics into child prompts unless needed for that role. |

## Reference map

Load references with `skill_view(name="idea-spark:idea-spark-usage", file_path="...")` when supported. If a plugin-bundled reference request returns this main SKILL again, use `read_file` on `idea_spark/resources/skills/idea-spark-usage/<reference-path>` in the Idea-Spark plugin source tree.

- `references/parent-controller.md` — parent-only continuous r1 → r2 → r3 → r4 controller, phase verification, retries, and mandatory skill re-read checkpoints.
- `references/subagent-contract.md` — child-only join/read/write/link/message rules, allowed toolsets, artifact expectations, and prompt checklist.
- `references/cli-dashboard.md` — CLI-first calls, optional tool-mode, dashboard link health checks, public operation names, artifact/gate types, and safety boundary.
- `references/handoff-report.md` — standalone readable report requirements, self-containment scan, and distinction between ledger export and human handoff.

## [PARENT-ONLY] Parent workflow, short form

Do not follow this section from a subagent prompt unless explicitly assigned to orchestrate the room.

1. Create one room and seed durable `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` artifacts.
2. Launch `r1/review` children such as `PriorArtBreaker`, `FeasibilityBreaker`, `SkepticalAC`, and `ExperimentPlanner`; every child writes at least one message and at least one typed artifact.
3. Verify r1 by reading room status/messages/artifacts.
4. **Re-read this SKILL.md with `skill_view(name="idea-spark:idea-spark-usage")` before launching r2.** Use the current checklist below to confirm r1 is not terminal.
5. Launch `r2/rebuttal` and repair roles such as `AuthorAdvocate`, `SchemaSurgeon`, `ExperimentPlanner`, or `BaselineRepair`; r2 reads r1 artifacts and writes `Rebuttal`, `RevisionPlan`, `ExperimentPlan`, `BenchmarkRequirement`, or `RegimeTransition` artifacts.
6. Verify r2, retry a missing required role once with a narrower prompt if it joined but wrote no artifacts, then **re-read this SKILL.md** before launching r3.
7. Launch `r3/re-review` roles such as prior-art re-review, feasibility re-review, skeptical AC, and open-need curator; r3 writes `MetaReview`, `ScoreCard`, and/or `OpenNeed` updates.
8. Verify r3 and **re-read this SKILL.md** before launching r4.
9. Launch `r4/gate`; Gatekeeper must write final `ScoreCard` / `MetaReview` and call `idea_spark_gate_record(close_room=true)`.
10. Stop only after `idea_spark_room_status` reports `has_terminal_gate=true`.
11. Export the deterministic ledger with `idea_spark_room_export`, then write a standalone handoff report when the user needs to share results outside the room.

## [PARENT-ONLY] Mandatory phase re-read checkpoint

Idea-Spark runs create long context. The parent/main agent must not rely on memory after a long child-agent round.

After **each** phase (`r1`, `r2`, `r3`, and before final reporting), the parent must:

1. Read room status and verify the expected messages/artifacts for the phase.
2. Call `skill_view(name="idea-spark:idea-spark-usage")` again.
3. Use this checklist to decide the next action:
   - If r1 is complete and no terminal gate exists, launch r2; do not summarize as done.
   - If r2 is complete and no terminal gate exists, launch r3; retry missing repair roles once if needed.
   - If r3 is complete and no terminal gate exists, launch r4 Gatekeeper.
   - If r4 recorded a real gate and `has_terminal_gate=true`, export and write the handoff report when needed.
   - If a required source, tool, or safety decision is missing, record an `OpenNeed` or ask the user only for that blocker.

## [PARENT-ONLY] Discussion-until-gate stop rule

- `r1`, `r2`, and `r3` are never terminal phases.
- Do not stop after r1/r2/r3; continue to the next phase after verification and the mandatory skill re-read checkpoint.
- A child summary, parent synthesis, dashboard text, exported ledger, or message saying “accepted” is not a gate.
- Stop only when room status says `has_terminal_gate=true` from a real `idea_spark_gate_record` row and paired `GateDecision` artifact.
- If `max_rounds=4` is exhausted without enough evidence, record a real `needs_more_evidence` gate at r4 instead of stopping early.

## Hard boundary: [PARENT-ONLY] vs [SUBAGENT-ONLY]

- **[PARENT-ONLY] The parent** creates the room, starts or checks the dashboard when needed, launches delegates, verifies every phase, re-reads this skill between phases, decides retries, records or delegates the terminal gate, exports the ledger, and writes the standalone handoff report.
- **[SUBAGENT-ONLY] A subagent** handles one bounded role. It joins the room, reads current ledger state, writes its message/artifacts/open needs, verifies its own writes, returns a summary, and stops.
- **[SUBAGENT-ONLY] Subagents must not** assume they are persistent room members. They should not call `skill_manage`, spawn more agents, export the final report, or decide that the whole room is complete unless assigned Gatekeeper and explicitly instructed to call `idea_spark_gate_record`.

## Minimal role/tool rules

- Default child delegate toolsets are `toolsets=["terminal", "file", "skills"]`; add external toolsets only when that role needs outside evidence.
- Explicit tool-mode child toolsets are `toolsets=["idea_spark", "skills"]` only after config enablement and session reset.
- Every substantive child writes at least one `idea_spark_message_post` and one typed artifact.
- Prefer artifact links over vague references to “previous reviewer”.
- Open evidence gaps use `idea_spark_need_create` / `idea_spark_need_update`.
- Final decisions use `idea_spark_gate_record`; message-only gates are invalid.

## Human handoff rule

`idea_spark_room_export` is an internal ledger export, not automatically a researcher-ready report. When the user asks for a report or the output will be handed to someone who cannot inspect the room, write a standalone Markdown report after the terminal gate and scan it for local paths, URLs, room IDs, artifact IDs, need IDs, and gate IDs, plus “see file/path” wording before delivery.
