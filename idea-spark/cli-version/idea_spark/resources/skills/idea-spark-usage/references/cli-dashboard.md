# CLI, Tool Mode, Dashboard, and Ledger Reference

Use this reference when you need exact Idea-Spark command mechanics, dashboard handling, artifact types, or safety boundaries.

## Default CLI-first operations

Use JSON files for substantive payloads because artifacts and messages often contain multiline Markdown, tables, and quotes.

```bash
hermes idea-spark call idea_spark_room_create --json-file /tmp/room.json
hermes idea-spark call idea_spark_room_join --json-file /tmp/join.json
hermes idea-spark call idea_spark_artifact_create --json-file /tmp/artifact.json
hermes idea-spark call idea_spark_message_post --json-file /tmp/message.json
hermes idea-spark call idea_spark_gate_record --json-file /tmp/gate.json
hermes idea-spark call idea_spark_room_export --json-file /tmp/export.json
```

`--stdin` is acceptable when a previous command emits one JSON object.

## Public operation names

Supported public operations include room create/join/status/read/export, message post/read, artifact create/read/link/status update, gate record, need create/update, and round wait. Do not invent private operations such as `need_read`; use room status, room export, message read, or artifact read instead.

## Dashboard link rule

After every successful `idea_spark_room_create`, surface the returned room URL only after the dashboard is reachable or clearly label it as unverified. If a dashboard is already running on a non-default port, pass `dashboard_base_url` in the create payload. Pass `check_dashboard=true` to receive `dashboard_checked`, `dashboard_reachable`, `dashboard_snapshot_url`, or `dashboard_warning`.

Start the local dashboard from the Idea-Spark source tree when needed:

```bash
python3 -m idea_spark.dashboard --host 127.0.0.1 --port 8765
```

The dashboard is localhost-only by default. It shows rooms, joined subagents, missing expected agents, messages, artifacts, gate decisions, and open needs. It is a monitor, not an agent launcher.

## Optional tool-mode

Default mode is skill + CLI. Direct `idea_spark_*` Hermes tools are not registered unless plugin config explicitly enables them and the Hermes session has been restarted/reset.

```bash
hermes idea-spark config set-tools true
# then start a fresh Hermes process or session reset
```

Disable tool-mode with:

```bash
hermes idea-spark config set-tools false
```

When explicit tool-mode is active, narrow ledger-only child roles can use `toolsets=["idea_spark", "skills"]`. Otherwise use CLI-first `toolsets=["terminal", "file", "skills"]`.

## Round wait

Use `idea_spark_round_wait` with finite `timeout_s`. For strict phase barriers pass `phase`; for a whole-round parent barrier omit `phase` or pass `phase="*"`; for role-specific labels in one barrier pass `phases=[...]`. Continue with partial state on timeout and record missing agents explicitly.

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

Idea-Spark CLI operations and optional tools operate on the SQLite ledger, plugin config, and Markdown export payloads. They do not run web, shell, terminal, browser, file-system automation, or network actions on behalf of the review. The parent controls external tool access through `delegate_task` toolsets.
