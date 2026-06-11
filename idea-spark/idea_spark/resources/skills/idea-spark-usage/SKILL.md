---
name: idea-spark-usage
description: Use the Idea-Spark Hermes plugin to coordinate delegate_task child agents through typed artifact debate rooms, gates, open needs, and deterministic Markdown export.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [idea-spark, delegate_task, multi-agent, research-review, hermes-plugin]
---

# Idea-Spark Usage

Load this when the task asks to run, coordinate, inspect, or explain an Idea-Spark review room.

Idea-Spark is a Hermes standalone plugin/toolset named `idea_spark`. It is not a subagent launcher. The parent agent launches children with `delegate_task`; Idea-Spark gives those agents a shared SQLite ledger.

## Core protocol

1. Parent creates one room with `idea_spark_room_create`.
2. Parent seeds durable starting artifacts such as `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` with `idea_spark_artifact_create`.
3. Parent delegates child roles with at least the `idea_spark` toolset. Add other toolsets only when needed, e.g. `web`, `file`, or `terminal`.
4. Every child must first call `idea_spark_room_join` using its assigned `room_id`, `agent_id`, and `role`.
5. Children read current state with `idea_spark_room_status`, `idea_spark_message_read`, and `idea_spark_artifact_read` before writing.
6. Children create typed artifacts for claims, objections, evidence, rebuttals, risks, experiments, score cards, meta-reviews, and open needs.
7. Children link provenance with `idea_spark_artifact_link` instead of relying on free-text memory.
8. Use `idea_spark_round_wait` with finite `timeout_s`; on timeout, continue with partial state and explicitly record missing agents.
9. Final conclusions require `idea_spark_gate_record`; do not treat chat consensus as a final decision.
10. Parent exports the deterministic Markdown report with `idea_spark_room_export`.

## Recommended round-based work mode

Default to parent-orchestrated, round-based debate. `delegate_task` children are short-lived workers: they receive one bounded task from the parent, join the room, read the ledger, write messages/artifacts, return a summary to the parent, and then stop. Do not assume subagents remain online as persistent chat-room members unless a separate long-running runner/daemon has been explicitly built for that task.

Use the Idea-Spark room as the durable shared memory between these short-lived children. A child can respond to other agents only by reading what those agents already wrote into the room, then writing its own message, artifact, link, rebuttal, score, need, or gate record. The parent creates the multi-turn discussion by launching more rounds after reading the room state.

Preferred default sequence:

1. `r0/seed`: Parent creates the room, sets `metadata.expected_agents`, and seeds `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` artifacts.
2. `r1/review`: Launch independent reviewers in parallel, usually `PriorArtBreaker`, `FeasibilityBreaker`, `SkepticalAC`, and `ExperimentPlanner`. Each child joins, reads the seed artifacts, posts a concise room message, and creates typed objections/evidence/risks/plans.
3. `r2/rebuttal`: Launch response and repair roles, usually `AuthorAdvocate`, `SchemaSurgeon`, and optionally `ExperimentPlanner` again. Each child reads `NoveltyObjection`, `FeasibilityObjection`, `ReviewerRisk`, and prior messages, then writes `Rebuttal`, `RevisionPlan`, `ExperimentPlan`, or `OpenNeed` artifacts that explicitly cite or link the artifacts they address.
4. `r3/gate`: Launch `MetaReviewer` and/or `Gatekeeper`. They read the whole ledger, produce `ScoreCard`/`MetaReview` artifacts, and record the final decision with `idea_spark_gate_record`.
5. Export with `idea_spark_room_export` only after the gate decision or an explicit `needs_more_evidence` outcome is recorded.

For live-room readability, require every child to write at least one `idea_spark_message_post` narrative update and at least one durable typed artifact when it has substantive content. Prefer artifact links over vague references such as “the previous reviewer said”. Use `idea_spark_round_wait` only as a finite barrier; on timeout, continue with partial state, record missing expected agents, and avoid blocking the whole discussion indefinitely.

When the user asks for “subagents discussing with each other,” use this round-based pattern by default rather than trying to keep `delegate_task` children alive. Use a persistent multi-process runner only when the user explicitly asks for always-on agents that poll the room and continue replying over time.

## Recommended roles

Typical ML idea review roles:

- `PriorArtBreaker`
- `FeasibilityBreaker`
- `SkepticalAC`
- `AuthorAdvocate`
- `ExperimentPlanner`
- `Gatekeeper`
- `SchemaSurgeon`
- `MetaReviewer`

Keep `metadata.expected_agents` no larger than the current `delegation.max_concurrent_children` when strict barriers are required. Otherwise use timeout-only soft barriers.

## Minimal parent flow

```text
1. idea_spark_room_create({
   "title": "...",
   "topic": "...",
   "metadata": {"expected_agents": ["prior", "feasibility", "gatekeeper"]}
})
2. idea_spark_artifact_create(room_id=..., type="ResearchGoal", title=..., content={...})
3. delegate_task children with toolsets=["idea_spark", ...]
4. idea_spark_round_wait(room_id=..., round_id="r1", phase="review", timeout_s=60)
5. idea_spark_room_status(room_id=...)
6. idea_spark_room_export(room_id=..., format="markdown")
```

## Realtime browser dashboard

When the user wants to watch subagents while they are discussing, start the local read-only dashboard from the Idea-Spark source tree:

```bash
cd /home/xu/project/autosci-delphi/idea-spark
python3 -m idea_spark.dashboard --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765/
```

For a specific room:

```text
http://127.0.0.1:8765/room/<room_id>
```

The dashboard reads the same SQLite ledger used by the tools. It shows rooms, joined subagents, missing expected agents, live messages, artifacts, gate decisions, and open needs. Room pages use `EventSource` / SSE for near-real-time updates and fall back to browser polling. The top-right `EN` / `中文` switch changes dashboard UI labels in-place and persists the preference in browser local storage; it does not translate room titles or agent-authored discussion content.

Safety boundary:

- The dashboard is localhost-only by default and read-only.
- It accepts GET/HEAD/OPTIONS; mutation methods return 405.
- It is a CLI-started monitor, not a Hermes tool handler that launches web/server actions.
- Use `--db /absolute/path/to/idea_spark.sqlite3` or `IDEA_SPARK_DB=...` for a non-default ledger.

## Child prompt checklist

Each child prompt should include:

- Room id.
- Stable agent id.
- Role name.
- Required first action: `idea_spark_room_join`.
- Round id and phase naming convention.
- Required artifact types for that role.
- Whether external tools are allowed.
- Requirement to record missing evidence through `idea_spark_need_create`.
- Requirement to use `idea_spark_gate_record` only for explicit gate decisions.

## Artifact types

Allowed artifact types are:

`ResearchGoal`, `IdeaCard`, `EvaluationRubric`, `AtomicClaim`, `Assumption`, `PriorArtEvidence`, `EvidenceLink`, `NoveltyObjection`, `FeasibilityObjection`, `ReviewerRisk`, `Rebuttal`, `RevisionPlan`, `ExperimentPlan`, `StressTest`, `BenchmarkRequirement`, `ScoreCard`, `GateDecision`, `OpenNeed`, `RegimeTransition`, `MetaReview`.

Allowed statuses: `proposed`, `accepted`, `rejected`, `superseded`, `retracted`, `stale`.

Gate decisions: `accepted`, `rejected`, `superseded`, `retracted`, `needs_more_evidence`.

## Safety boundary

Idea-Spark tools only operate on their SQLite ledger and Markdown export. They do not run web, shell, terminal, browser, file-system automation, or network actions. Give child agents external toolsets explicitly through `delegate_task` when needed.
