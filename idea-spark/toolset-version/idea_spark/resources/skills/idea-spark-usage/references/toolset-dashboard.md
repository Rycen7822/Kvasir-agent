# Toolset, Dashboard, and Ledger Reference

Use this reference when you need exact Idea-Spark direct-tool mechanics, dashboard handling, artifact types, or safety boundaries.

## Direct toolset operations

The toolset-version plugin registers these direct Hermes tools in the `idea_spark` toolset after the plugin is enabled and the session is fresh:

```text
idea_spark_room_create
idea_spark_room_join
idea_spark_room_status
idea_spark_message_post
idea_spark_message_read
idea_spark_round_wait
idea_spark_artifact_create
idea_spark_artifact_read
idea_spark_artifact_link
idea_spark_artifact_status_update
idea_spark_gate_record
idea_spark_need_create
idea_spark_need_update
idea_spark_room_export
```

Only these public operation names are supported. Do not invent private operations such as `need_read`; use room status, room export, message read, or artifact read instead.

## Toolset availability

After enabling the plugin, start a fresh Hermes process or reset the session before expecting the `idea_spark` toolset to appear. Existing sessions do not gain newly enabled tools mid-context.

Default child roles should use:

```text
toolsets=["idea_spark", "skills"]
```

Add `web`, `browser`, `file`, `terminal`, or other toolsets only when a role needs external evidence, local files, or shell checks.

## Dashboard rule

Start the local dashboard from the Idea-Spark source tree when needed:

```bash
python3 -m idea_spark.dashboard --host 127.0.0.1 --port 8765
```

The dashboard is localhost-only by default. It is a read-only monitor for rooms, joined subagents, missing expected agents, messages, artifacts, gate decisions, and open needs. It uses `EventSource` / SSE for near-real-time room updates and falls back to polling. The `EN` / `中文` switch changes dashboard UI labels in-place and persists in browser local storage. It is a monitor, not an agent launcher.

## Round wait

Use `idea_spark_round_wait` with finite `timeout_s`. For strict phase barriers pass `phase`; for a whole-round parent barrier omit `phase` or pass `phase="*"`; for role-specific labels in one barrier pass `phases=[...]` if supported by the current handler. Continue with partial state on timeout and record missing agents explicitly.

## Artifact types and statuses

Allowed artifact types:

```text
ResearchGoal, IdeaCard, EvaluationRubric, AtomicClaim, Assumption, PriorArtEvidence, EvidenceLink, NoveltyObjection, FeasibilityObjection, ReviewerRisk, Rebuttal, RevisionPlan, ExperimentPlan, StressTest, BenchmarkRequirement, ScoreCard, GateDecision, OpenNeed, RegimeTransition, MetaReview
```

Allowed artifact statuses:

```text
proposed, accepted, rejected, superseded, retracted, stale
```

Gate decisions:

```text
accepted, rejected, superseded, retracted, needs_more_evidence
```

## Safety boundary

Idea-Spark tool handlers operate on the SQLite ledger and Markdown export payloads. They do not run web, shell, terminal, browser, file-system automation, or network actions on behalf of the review. The parent controls external tool access through `delegate_task` toolsets.
