# Idea-Spark

Idea-Spark is a Hermes standalone plugin for typed artifact debate rooms. It gives parent agents and `delegate_task` child agents a shared SQLite ledger for ML research idea review.

## What Idea-Spark is

Idea-Spark is a storage/export plugin named `idea-spark`. Its Python package and Hermes toolset are `idea_spark`. It records rooms, participants, messages, typed artifacts, artifact links, gate records, open needs, and deterministic Markdown exports.

The runtime model is shared-ledger coordination. A parent creates a room, seeds initial artifacts, launches child agents with the `idea_spark` toolset, and exports a report from ledger state.

## What it is not

Idea-Spark is not a chat transcript summarizer. It is not a scheduler, ranking engine, vector database, or autonomous web/file/terminal executor. Same-turn child discussion is SQLite shared-ledger coordination, not P2P socket chat. The optional realtime dashboard is a local management viewer over that ledger; it is started explicitly from the CLI and is not launched by Hermes tool handlers.

## Tool list

- `idea_spark_room_create`
- `idea_spark_room_join`
- `idea_spark_room_status`
- `idea_spark_message_post`
- `idea_spark_message_read`
- `idea_spark_round_wait`
- `idea_spark_artifact_create`
- `idea_spark_artifact_read`
- `idea_spark_artifact_link`
- `idea_spark_artifact_status_update`
- `idea_spark_gate_record`
- `idea_spark_need_create`
- `idea_spark_need_update`
- `idea_spark_room_export`

Only these public tool names are supported.

## Data model

Core entities:

- Rooms hold the review topic, protocol metadata, and expected agents.
- Participants record child agent presence.
- Messages store concise round/phase transcript entries and linked artifact IDs.
- Artifacts store typed scientific claims, objections, rebuttals, risks, experiment plans, gate decisions, and schema transitions.
- Artifact links store provenance and lifecycle relations such as `supports`, `rebuts`, `supersedes`, and `decomposes`.
- Gates store explicit accept/reject/supersede/retract/needs-more-evidence decisions.
- Open needs store unresolved evidence requests with pressure scores.

Final conclusions require `GateDecision` / `idea_spark_gate_record` evidence.

## Install

From this source tree:

```bash
mkdir -p "$HERMES_HOME/plugins/idea_spark"
cp -r idea_spark/* "$HERMES_HOME/plugins/idea_spark/"
```

Default storage path:

```text
$HERMES_HOME/idea-spark/idea_spark.sqlite3
```

Environment overrides:

```text
IDEA_SPARK_DB=/absolute/path/to/idea_spark.sqlite3
IDEA_SPARK_EXPORT_DIR=/absolute/path/for/future/file_exports
```

## Enable and restart

Enable the plugin:

```bash
hermes plugins enable idea-spark
```

After enabling, start a fresh Hermes process or session reset before expecting the new toolset to appear. Existing sessions do not gain newly enabled tools mid-context.

The plugin also registers a bundled usage skill. In a fresh session, load it explicitly when you need the protocol:

```python
skill_view(name="idea-spark:idea-spark-usage")
```

Plugin-bundled skills are qualified-only and may not appear in the flat skills list.

## Quick smoke test

In a fresh session with the plugin enabled, call this flow:

1. `idea_spark_room_create` with a title and topic.
2. `idea_spark_room_join` as a child agent.
3. `idea_spark_artifact_create` for a `ResearchGoal` or `IdeaCard`.
4. `idea_spark_message_post` linked to the artifact.
5. `idea_spark_room_export` with `format="markdown"`.

The export must return Markdown with the fixed report sections.

## Realtime browser dashboard

Start the local management dashboard from this source tree:

```bash
cd /home/xu/project/autosci-delphi/idea-spark
python3 -m idea_spark.dashboard --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

A room-specific URL is:

```text
http://127.0.0.1:8765/room/<room_id>
```

The dashboard reads the same SQLite ledger as the Hermes tools. It shows rooms, joined subagents, missing expected agents, messages, artifacts, gate records, and open needs. Room pages use `EventSource` / SSE for near-real-time updates and fall back to browser polling if SSE is unavailable. The top-right `EN` / `中文` switch changes the dashboard UI language in-place and stores the preference in browser local storage; room titles and agent-authored content are left unchanged. Local room deletion is available only through the explicit room management path guarded by `room_delete_enabled` and a `confirm=<room_id>` query.

Dashboard safety boundary:

- Localhost bind by default: `127.0.0.1`.
- The dashboard does not edit messages, artifacts, gates, open needs, or participant rows directly.
- GET/HEAD/OPTIONS are available for monitoring; DELETE is limited to `/api/rooms/<room_id>?confirm=<room_id>` for local room cleanup.
- No npm build, external web service, authentication layer, or remote hosting is included in this MVP.

Use `IDEA_SPARK_DB=/absolute/path/to/idea_spark.sqlite3` or `--db /absolute/path/to/idea_spark.sqlite3` when monitoring a non-default ledger.

## Parent protocol

1. Create the room with `idea_spark_room_create`.
2. Seed `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` artifacts with `idea_spark_artifact_create`.
3. Launch child roles with `toolsets=["idea_spark", "skills"]` by default: PriorArtBreaker, FeasibilityBreaker, SkepticalAC, AuthorAdvocate, ExperimentPlanner, Gatekeeper, SchemaSurgeon, and MetaReviewer. Add external toolsets only for roles that need outside evidence.
4. Run a bounded `discussion-until-gate` loop with `max_rounds=4` and this phase order: `Seed / Framing`, `Novelty Attack`, `Weakness / Feasibility Attack`, `Author Rebuttal / Improvement Draft`, `Re-review / Cross-examination`, `Gate`.
5. After each phase, use `idea_spark_room_status` and `idea_spark_message_read` to monitor progress and continue while `has_terminal_gate=false`.
6. Require `idea_spark_gate_record` before treating any conclusion as final; message-only gate is not final.
7. On the terminal decision, call `idea_spark_gate_record` with `close_room=true`.
8. Use `idea_spark_room_export` to produce the final Markdown report.

Strict barriers require `expected_agents <= delegation.max_concurrent_children`; otherwise use timeout-only soft barriers.

## Child protocol

1. First call `idea_spark_room_join` with the assigned `room_id`, `agent_id`, and role.
2. Read the current room state with `idea_spark_room_status`, `idea_spark_message_read`, and `idea_spark_artifact_read`.
3. Create typed artifacts with `idea_spark_artifact_create` for claims, objections, rebuttals, evidence, risks, experiment plans, and score cards.
4. Link provenance with `idea_spark_artifact_link`.
5. Post concise narrative updates with `idea_spark_message_post` and include artifact IDs.
6. Update lifecycle status explicitly with `idea_spark_artifact_status_update`.
7. Use `idea_spark_need_create` for missing evidence or unresolved reviewer risk; use `idea_spark_need_update` to claim, resolve, reopen, stale, or cancel those needs.
8. Use `idea_spark_round_wait` with a finite timeout, then continue with partial state if peers are missing.
9. Use `idea_spark_gate_record` for final gate decisions; no consensus without GateDecision and message-only gate is not final.

## Failure modes

- Missing expected agents: continue after `idea_spark_round_wait` returns timeout and record missing agents explicitly.
- Duplicate artifacts: `idea_spark_artifact_create` returns the existing artifact ID with `deduplicated=true`.
- Invalid type, relation, status, or gate decision: handlers return JSON with `success=false`.
- SQLite contention: writes use short transactions and bounded retry.
- Toolset absent: enable the plugin and start a fresh Hermes process or session reset.

## Safety boundary

`idea-spark` handlers do not execute web, terminal, file, shell, subprocess, browser, or network actions. Role agents receive external toolsets through parent-controlled `delegate_task` calls, not through this plugin.

## Development and tests

Run from `/home/xu/project/autosci-delphi/idea-spark`:

```bash
python3 -m pytest tests/ -q
```

Focused gates:

```bash
python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py -q
python3 -m pytest tests/test_store_migrations.py -q
python3 -m pytest tests/test_tools_room.py tests/test_export.py -q
python3 -m pytest tests/test_tools_artifacts_gates.py -q
python3 -m pytest tests/test_dashboard.py tests/test_examples_contract.py -q
```

## Phase locks

MVP includes the room/message barrier, typed artifact ledger, gates, open needs, fixed Markdown export, protocol examples, and plugin discovery checks.

Locked until the ledger/export/dashboard gates pass:

- Pairwise tournaments and Elo.
- ArtifactReactor scheduling.
- Vector retrieval or embedding cache.
- Remote or authenticated dashboard hosting.
- Alternate public tool names.
