# Idea-Spark

Idea-Spark is a Hermes plugin family for typed artifact debate rooms. It gives parent agents and `delegate_task` child agents a shared SQLite ledger for ML research idea review, with deterministic Markdown exports, gate records, open needs, and an optional localhost dashboard.

This top-level README is now the entry point for two preserved Idea-Spark variants. Choose one variant before installing or testing; the recommended implementation packages and detailed docs live in `cli-version/` and `toolset-version/`.

## Which version should I use?

| Path | Default registration | Best fit |
| --- | --- | --- |
| `cli-version/` | Bundled skill `idea-spark:idea-spark-usage` + `hermes idea-spark` CLI; the 14 `idea_spark_*` tools are off unless explicitly enabled by config. | Default/recommended Hermes profile usage. Keeps ordinary sessions cheaper and lets parent/child agents coordinate through JSON payload files and the shared ledger. |
| `toolset-version/` | Bundled skill + all 14 `idea_spark_*` Hermes tools in the `idea_spark` toolset. No plugin CLI registration. | Narrow high-throughput child-agent runs where every participant should call ledger tools directly. |

See `VERSION_SPLIT.md` for the preservation notes and registration smoke expectations. See each variant README for full operational details:

- `cli-version/README.md`
- `toolset-version/README.md`

## What Idea-Spark is

Idea-Spark is a storage/export plugin named `idea-spark`. Its Python package and Hermes toolset are `idea_spark`. It records rooms, participants, messages, typed artifacts, artifact links, gate records, open needs, and deterministic Markdown exports.

The coordination model is shared-ledger review, not peer-to-peer chat. A parent creates a room, seeds initial artifacts, launches child agents, waits through bounded discussion rounds, records terminal gate decisions, and exports a report from ledger state.

## What it is not

Idea-Spark is not a chat transcript summarizer, scheduler, ranking engine, vector database, or autonomous web/file/terminal executor. The plugin handlers operate on the SQLite ledger, plugin config, and Markdown export payloads. Role agents receive external toolsets through parent-controlled `delegate_task` calls, not through this plugin.

The optional realtime dashboard is a local management viewer over the same ledger. It is started explicitly from the CLI/Python module and is not launched by Hermes tool handlers.

## Canonical operations

Both variants use the same public operation names:

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

Only these public operation/tool names are supported.

## Install a variant

For current workflows, install from the variant directory you intend to run. A checkout may also contain historical root files; prefer the variant directories unless you are intentionally debugging those legacy files.

CLI-first variant:

```bash
cd /path/to/autosci-delphi/idea-spark/cli-version
mkdir -p "$HERMES_HOME/plugins/idea_spark"
cp -r idea_spark/. "$HERMES_HOME/plugins/idea_spark/"
hermes plugins enable idea-spark
```

Toolset-first variant:

```bash
cd /path/to/autosci-delphi/idea-spark/toolset-version
mkdir -p "$HERMES_HOME/plugins/idea_spark"
cp -r idea_spark/. "$HERMES_HOME/plugins/idea_spark/"
hermes plugins enable idea-spark
```

If you switch between variants, clear or replace the plugin copy so stale files from the previous variant do not remain in `$HERMES_HOME/plugins/idea_spark`.

After enabling or switching variants, start a fresh Hermes process or reset the session before expecting new skills, CLI commands, or tool registrations to appear. Existing sessions do not gain or lose plugin surfaces mid-context.

## Storage and config

Default storage path:

```text
$HERMES_HOME/idea-spark/idea_spark.sqlite3
```

Default config path for CLI-first tool registration:

```text
$HERMES_HOME/idea-spark/config.json
```

Environment overrides:

```text
IDEA_SPARK_DB=/absolute/path/to/idea_spark.sqlite3
IDEA_SPARK_EXPORT_DIR=/absolute/path/for/future/file_exports
```

In `cli-version/`, the plugin registers the bundled skill and CLI by default. The direct Hermes tools are config-gated:

```bash
hermes idea-spark config set-tools true
hermes idea-spark config set-tools false
```

`platform_toolsets` entries alone are not enough for `cli-version/`; the plugin must also see `tools.enabled=true` in its own config before it calls `ctx.register_tool(...)`.

## CLI-first quick flow

Use JSON files for substantive payloads. Room artifacts often contain multiline Markdown, tables, and quotes, so `--json-file` is safer than shell-escaping long inline arguments.

```bash
cd /path/to/autosci-delphi/idea-spark/cli-version

cat > /tmp/is_room.json <<'JSON'
{"room_id":"smoke-room","title":"Smoke room","topic":"CLI-first Idea-Spark smoke","created_by":"parent"}
JSON
hermes idea-spark call idea_spark_room_create --json-file /tmp/is_room.json

cat > /tmp/is_artifact.json <<'JSON'
{"room_id":"smoke-room","type":"ResearchGoal","title":"Smoke goal","content":"Prove CLI dispatch works.","created_by":"parent"}
JSON
hermes idea-spark call idea_spark_artifact_create --json-file /tmp/is_artifact.json

cat > /tmp/is_export.json <<'JSON'
{"room_id":"smoke-room","format":"markdown"}
JSON
hermes idea-spark call idea_spark_room_export --json-file /tmp/is_export.json
```

When a live dashboard URL should be openable, include `dashboard_base_url` and `check_dashboard=true` in the room-create payload, then give the returned `room_url` to the user only if `dashboard_reachable=true` or after separately verifying the dashboard.

## Toolset-first quick flow

Use this variant only when you intentionally want the 14 `idea_spark_*` tools available in the Hermes context. Launch child roles with `toolsets=["idea_spark", "skills"]` by default, and add external toolsets only for roles that need outside evidence.

A minimal flow is:

1. `idea_spark_room_create` with a title and topic.
2. `idea_spark_room_join` as each child agent.
3. `idea_spark_artifact_create` for `ResearchGoal`, `IdeaCard`, or `EvaluationRubric` records.
4. `idea_spark_message_post` with linked artifact IDs.
5. `idea_spark_gate_record` for terminal accept/reject/supersede/retract/needs-more-evidence decisions.
6. `idea_spark_room_export` with `format="markdown"`.

Message-only gate conclusions are not final; final conclusions require `GateDecision` / `idea_spark_gate_record` evidence.

## Dashboard

Start the local management dashboard from the selected variant directory:

```bash
cd /path/to/autosci-delphi/idea-spark/cli-version
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

The dashboard reads the same SQLite ledger as the CLI and optional Hermes tools. It shows rooms, joined subagents, missing expected agents, messages, artifacts, gate records, and open needs. Room pages use `EventSource` / SSE for near-real-time updates and fall back to browser polling if SSE is unavailable.

Dashboard safety boundary:

- Localhost bind by default: `127.0.0.1`.
- The dashboard does not edit messages, artifacts, gates, open needs, or participant rows directly.
- GET/HEAD/OPTIONS are available for monitoring; DELETE is limited to `/api/rooms/<room_id>?confirm=<room_id>` for local room cleanup.
- No npm build, external web service, authentication layer, or remote hosting is included in this MVP.

Use `IDEA_SPARK_DB=/absolute/path/to/idea_spark.sqlite3` or `--db /absolute/path/to/idea_spark.sqlite3` when monitoring a non-default ledger.

## Parent and child protocol notes

Recommended CLI-first parent flow:

1. Create the room with `hermes idea-spark call idea_spark_room_create --json-file room.json`.
2. Seed `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` artifacts.
3. Launch child roles with `toolsets=["terminal", "file", "skills"]` so they can write payload JSON files, call `hermes idea-spark`, and load the bundled skill. Put transient payload JSON under `/tmp/idea_spark_<run_id>/<agent_id>/`, not in the repo root.
4. Run a bounded `discussion-until-gate` loop with `max_rounds=4` and phase order `Seed / Framing`, `Novelty Attack`, `Weakness / Feasibility Attack`, `Author Rebuttal / Improvement Draft`, `Re-review / Cross-examination`, `Gate`.
5. After each phase, inspect `idea_spark_room_status` and `idea_spark_message_read`; continue while `has_terminal_gate=false`.
6. Record a terminal `idea_spark_gate_record` with `close_room=true` before exporting the final report.

Recommended child behavior:

- Join first with the assigned `room_id`, `agent_id`, and role.
- Read room status, messages, and artifacts before writing.
- Create typed artifacts for claims, objections, rebuttals, evidence, risks, experiment plans, and score cards.
- Link provenance with `idea_spark_artifact_link` and update lifecycle state with `idea_spark_artifact_status_update`.
- Use `idea_spark_need_create` / `idea_spark_need_update` for missing evidence or unresolved reviewer risks.
- Use `idea_spark_round_wait` with finite timeouts. For strict phase barriers pass `phase`; for whole-round parent barriers omit `phase` or pass `phase="*"`; for role-specific labels in one barrier pass `phases=[...]`.

Strict barriers require `expected_agents <= delegation.max_concurrent_children`; otherwise use timeout-only soft barriers and record missing agents explicitly.

## Development and tests

Run tests inside the selected variant:

```bash
cd /path/to/autosci-delphi/idea-spark/cli-version
python3 -m pytest tests/ -q

cd /path/to/autosci-delphi/idea-spark/toolset-version
python3 -m pytest tests/ -q
```

Focused smoke gates:

```bash
python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py -q
python3 -m pytest tests/test_store_migrations.py -q
python3 -m pytest tests/test_tools_room.py tests/test_export.py -q
python3 -m pytest tests/test_tools_artifacts_gates.py -q
python3 -m pytest tests/test_dashboard.py tests/test_examples_contract.py -q
```

## Phase locks

MVP includes the room/message barrier, typed artifact ledger, gates, open needs, fixed Markdown export, protocol examples, default CLI-first operation, explicit config-gated tool-mode, toolset-first preserved variant, dashboard checks, and plugin discovery checks.

Locked until the ledger/export/dashboard/config gates pass:

- Pairwise tournaments and Elo.
- ArtifactReactor scheduling.
- Vector retrieval or embedding cache.
- Remote or authenticated dashboard hosting.
- Alternate public tool names.
