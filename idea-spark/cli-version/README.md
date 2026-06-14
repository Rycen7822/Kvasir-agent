# Idea-Spark

Idea-Spark is a Hermes standalone plugin for typed artifact debate rooms. It gives parent agents and `delegate_task` child agents a shared SQLite ledger for ML research idea review.

## What Idea-Spark is

Idea-Spark is a storage/export plugin named `idea-spark`. Its Python package and optional Hermes toolset are `idea_spark`. It records rooms, participants, messages, typed artifacts, artifact links, gate records, open needs, and deterministic Markdown exports.

The default runtime model is CLI-first shared-ledger coordination. A parent creates a room, seeds initial artifacts, launches child agents, and exports a report from ledger state. The plugin registers its bundled skill and CLI by default; `idea_spark_*` Hermes tools are config-gated optional tools.

## What it is not

Idea-Spark is not a chat transcript summarizer. It is not a scheduler, ranking engine, vector database, or autonomous web/file/terminal executor. Same-turn child discussion is SQLite shared-ledger coordination, not P2P socket chat. The optional realtime dashboard is a local management viewer over that ledger; it is started explicitly from the CLI and is not launched by Hermes tool handlers.

## Default CLI-first mode

When the plugin loads with no extra config, it registers only:

- the bundled skill `idea-spark:idea-spark-usage`;
- the plugin CLI command `hermes idea-spark`.

It does **not** register the 14 `idea_spark_*` tools by default. This keeps ordinary Hermes sessions cheaper and avoids adding the Idea-Spark tool schemas to every context.

Default CLI operations dispatch the same ledger handlers that tool-mode uses. In a copy-installed Hermes plugin deployment, use the plugin subcommand:

```bash
hermes idea-spark config show
hermes idea-spark call idea_spark_room_create --json-file /tmp/room.json
hermes idea-spark call idea_spark_artifact_create --json-file /tmp/artifact.json
hermes idea-spark call idea_spark_room_export --json-file /tmp/export.json
```

Use JSON files for substantive payloads. Room artifacts often contain multiline Markdown, tables, and quotes, so `--json-file` is safer than shell-escaping long inline arguments. `--stdin` is available when another process writes one JSON object to standard input.

When the package is installed from this source tree as a Python project, the standalone console script `idea-spark` exposes the same subcommands; plugin-copy installs should rely on `hermes idea-spark ...`.

## Explicit tool-mode

Tool-mode is still supported for narrow high-throughput child agents, but it must be explicitly enabled with the profile-scoped plugin config file:

```text
$HERMES_HOME/idea-spark/config.json
```

Enable it with the CLI:

```bash
hermes idea-spark config set-tools true
```

Equivalent file content:

```json
{
  "tools": {
    "enabled": true
  }
}
```

After changing tool-mode, start a fresh Hermes process or session reset before expecting tool registration changes. Existing sessions do not gain or lose tools mid-context. `platform_toolsets` entries alone are not enough: the plugin must also see `tools.enabled=true` in its own config before it calls `ctx.register_tool(...)`.

Disable explicit tool-mode again with:

```bash
hermes idea-spark config set-tools false
```

## Tool list

These are the only public operation names. In default CLI-first mode they are used as `hermes idea-spark call <operation> --json-file payload.json`; in explicit tool-mode they can appear as Hermes tools under the `idea_spark` toolset.

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

Only these public tool/operation names are supported.

## Data model

Core entities:

- Rooms hold the review topic, protocol metadata, and expected agents.
- Participants record child agent presence.
- Messages store concise round/phase transcript entries and linked artifact IDs.
- Artifacts store typed scientific claims, objections, rebuttals, risks, experiment plans, gate decisions, and schema transitions.
- Artifact links store provenance and lifecycle relations such as `supports`, `rebuts`, `supersedes`, and `decomposes`.
- Gates store explicit accept/reject/supersede/retract/needs-more-evidence decisions.
- Open needs store unresolved evidence requests with pressure scores. In `idea_spark_room_status`, `counts.open_needs` means unresolved needs (`open` + `claimed`) and `counts.total_needs` means all need rows.

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

Default config path:

```text
$HERMES_HOME/idea-spark/config.json
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

After enabling, start a fresh Hermes process or session reset before expecting the bundled skill/CLI to appear in that session. Existing sessions do not gain newly enabled plugin surfaces mid-context.

The plugin registers a bundled usage skill. In a fresh session, load it explicitly when you need the protocol:

```python
skill_view(name="idea-spark:idea-spark-usage")
```

Plugin-bundled skills are qualified-only and may not appear in the flat skills list.

## CLI quick smoke test

Create payload files and call the CLI from `/path/to/idea-spark`:

```bash
cat > /tmp/is_room.json <<'JSON'
{"room_id":"smoke-room","title":"Smoke room","topic":"CLI-first Idea-Spark smoke","created_by":"parent"}
JSON
hermes idea-spark call idea_spark_room_create --json-file /tmp/is_room.json
# Copy the returned room_url to the user immediately only after the dashboard is started/verified; pass dashboard_base_url and check_dashboard=true when you want the CLI to report dashboard_reachable/dashboard_warning.

cat > /tmp/is_artifact.json <<'JSON'
{"room_id":"smoke-room","type":"ResearchGoal","title":"Smoke goal","content":"Prove CLI dispatch works.","created_by":"parent"}
JSON
hermes idea-spark call idea_spark_artifact_create --json-file /tmp/is_artifact.json

cat > /tmp/is_export.json <<'JSON'
{"room_id":"smoke-room","format":"markdown"}
JSON
hermes idea-spark call idea_spark_room_export --json-file /tmp/is_export.json
```

The export must return Markdown with the fixed report sections.

## Realtime browser dashboard

Start the local management dashboard from this source tree:

```bash
cd /path/to/idea-spark
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

Operational rule: every successful `idea_spark_room_create` response includes `room_url`, and the parent should give that concrete link to the user immediately after starting or verifying the dashboard server. If the dashboard is running on another port, pass `dashboard_base_url` so `room_url` points at the actual live room; pass `check_dashboard=true` to get `dashboard_checked`, `dashboard_reachable`, and either `dashboard_snapshot_url` or `dashboard_warning`. Do not imply that an unverified URL is openable.

The dashboard reads the same SQLite ledger as the CLI and optional Hermes tools. It shows rooms, joined subagents, missing expected agents, messages, artifacts, gate records, and open needs. Room pages use `EventSource` / SSE for near-real-time updates and fall back to browser polling if SSE is unavailable. The top-right `EN` / `中文` switch changes the dashboard UI language in-place and stores the preference in browser local storage; room titles and agent-authored content are left unchanged. Status views are read-only; local room deletion is available only through the explicit room management path guarded by `room_delete_enabled` and a `confirm=<room_id>` query.

Dashboard safety boundary:

- Localhost bind by default: `127.0.0.1`.
- The dashboard does not edit messages, artifacts, gates, open needs, or participant rows directly.
- GET/HEAD/OPTIONS are available for monitoring; DELETE is limited to `/api/rooms/<room_id>?confirm=<room_id>` for local room cleanup.
- No npm build, external web service, authentication layer, or remote hosting is included in this MVP.

Use `IDEA_SPARK_DB=/absolute/path/to/idea_spark.sqlite3` or `--db /absolute/path/to/idea_spark.sqlite3` when monitoring a non-default ledger.

## Parent protocol

Default CLI-first parent flow:

1. Create the room with `hermes idea-spark call idea_spark_room_create --json-file room.json`; include `dashboard_base_url` and `check_dashboard=true` when a live dashboard should be openable, then give the returned `room_url` to the user only if `dashboard_reachable=true` or after separately verifying the dashboard.
2. Seed `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` artifacts with `hermes idea-spark call idea_spark_artifact_create --json-file artifact.json`.
3. Launch child roles with `toolsets=["terminal", "file", "skills"]` by default so they can write payload JSON files, call `hermes idea-spark`, and load the bundled skill. Pass each child a `payload_scratch_dir` under `/tmp/idea_spark_<run_id>/<agent_id>/`; do not let transient payload JSON land in the repo root. Add external toolsets only for roles that need outside evidence.
4. Run a bounded `discussion-until-gate` loop with `max_rounds=4` and this phase order: `Seed / Framing`, `Novelty Attack`, `Weakness / Feasibility Attack`, `Author Rebuttal / Improvement Draft`, `Re-review / Cross-examination`, `Gate`.
5. After each phase, use `idea_spark_room_status` and `idea_spark_message_read` through CLI calls to monitor progress and continue while `has_terminal_gate=false`.
6. Require `idea_spark_gate_record` before treating any conclusion as final; message-only gate is not final.
7. On the terminal decision, call `idea_spark_gate_record` with `close_room=true`.
8. Use `idea_spark_room_export` to produce the final Markdown report.

Explicit tool-mode parent flow:

- Enable `$HERMES_HOME/idea-spark/config.json` with `tools.enabled=true`.
- Start a fresh Hermes process or session reset.
- Use `toolsets=["idea_spark", "skills"]` only for roles that should have the narrow ledger tools.

Strict barriers require `expected_agents <= delegation.max_concurrent_children`; otherwise use timeout-only soft barriers.

## Child protocol

Default CLI-first child protocol:

1. First call `hermes idea-spark call idea_spark_room_join --json-file join.json` with the assigned `room_id`, `agent_id`, and role.
2. Read the current room state with CLI calls to `idea_spark_room_status`, `idea_spark_message_read`, and `idea_spark_artifact_read`.
3. Create typed artifacts with `idea_spark_artifact_create` for claims, objections, rebuttals, evidence, risks, experiment plans, and score cards.
4. Link provenance with `idea_spark_artifact_link`.
5. Post concise narrative updates with `idea_spark_message_post` and include artifact IDs.
6. Update lifecycle status explicitly with `idea_spark_artifact_status_update`.
7. Use `idea_spark_need_create` for missing evidence or unresolved reviewer risk; use `idea_spark_need_update` to claim, resolve, reopen, stale, or cancel those needs.
8. Use `idea_spark_round_wait` with a finite timeout. For strict phase barriers pass `phase`; for a whole-round parent barrier omit `phase` or pass `phase="*"`; for role-specific labels in one barrier pass `phases=[...]`. Continue with partial state if peers are missing.
9. Use `idea_spark_gate_record` for final gate decisions; no consensus without GateDecision and message-only gate is not final.

When explicit tool-mode is enabled and the session has been reset, the same protocol can use direct Hermes tool calls instead of `hermes idea-spark call ...` commands.

## Failure modes

- Missing expected agents: continue after `idea_spark_round_wait` returns timeout and record missing agents explicitly.
- Duplicate artifacts: `idea_spark_artifact_create` returns the existing artifact ID with `deduplicated=true`.
- Invalid type, relation, status, or gate decision: handlers return JSON with `success=false`.
- SQLite contention: writes use short transactions and bounded retry.
- Toolset absent: use default CLI-first mode, or enable `$HERMES_HOME/idea-spark/config.json` with `tools.enabled=true` and start a fresh Hermes process or session reset.

## Safety boundary

`hermes idea-spark` CLI commands and optional tool handlers operate only on the SQLite ledger, plugin config file, and Markdown export payloads. They do not execute web, terminal, file, shell, subprocess, browser, or network actions on behalf of the review. Role agents receive external toolsets through parent-controlled `delegate_task` calls, not through this plugin.

## Development and tests

Run from `/path/to/idea-spark`:

```bash
python3 -m pytest tests/ -q
```

Focused gates:

```bash
python3 -m pytest tests/test_config.py tests/test_cli.py -q
python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py -q
python3 -m pytest tests/test_store_migrations.py -q
python3 -m pytest tests/test_tools_room.py tests/test_export.py -q
python3 -m pytest tests/test_tools_artifacts_gates.py -q
python3 -m pytest tests/test_dashboard.py tests/test_examples_contract.py -q
```

## Phase locks

MVP includes the room/message barrier, typed artifact ledger, gates, open needs, fixed Markdown export, protocol examples, default CLI-first operation, explicit config-gated tool-mode, and plugin discovery checks.

Locked until the ledger/export/dashboard/config gates pass:

- Pairwise tournaments and Elo.
- ArtifactReactor scheduling.
- Vector retrieval or embedding cache.
- Remote or authenticated dashboard hosting.
- Alternate public tool names.
