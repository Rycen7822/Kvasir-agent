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
