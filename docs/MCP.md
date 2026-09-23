# MCP research tools

Kvasir-agent exposes 24 public research tools through standard `tools/list`. Codex handles ordinary file/search/edit/shell/Git/test/build/process work. The bundled `.mcp.json` launches the server from the plugin directory.

Every public tool requires the absolute research directory as `project`. The server derives quest identity from that project's manifest; `project_root` and caller-supplied `quest_id` are not public parameters. Invalid arguments are rejected before invoking services. Install runtime dependencies with `python3 -m pip install -e .`.

## Domain operations

| Tool | Operations |
|---|---|
| `ka_research_read` | `status`, `resume`, `delta`, `review`, `methods` |
| `ka_memory_query` | `search`, `read`, `recent` |
| `ka_baseline` | `create`, `confirm`, `record` |
| `ka_environment` | `register`, `validate`, `show`, `validate_manifest` |
| `ka_trajectory_query` | `search`, `show` |
| `ka_method_record` | `idea`, `negative`, `result` |
| `ka_analysis` | `create`, `read`, `record_slice` |
| `ka_literature_setup` | `prepare`, `bibliography` |
| `ka_paper_record` | `outline`, `bundle` |

Pass `operation` along with that operation's fields. Do not combine fields from unrelated operations. A baseline `record` updates manifest readiness; it does not perform `confirm` validation. Mixed read/write tools have conservative write annotations.

## Independent tools

`ka_record_user_requirement`, `ka_checkpoint`, `ka_memory_write`, `ka_artifact_record`, `ka_artifact_index`, `ka_bash_exec`, `ka_log_digest`, `ka_trajectory_record`, `ka_feedback_ingest`, `ka_record_main_experiment`, `ka_claim_gate`, `ka_strict_research_upsert_candidate`, `ka_record_literature_reading_note`, `ka_paper_fetch`, `ka_paper_reliability_verify`.

Formal commands through `ka_bash_exec` require command class, provenance reason, experiment/artifact identity, working-directory policy and expected outputs or evidence paths. Baseline protection, environment validation, feedback reconciliation, novelty input checks and evidence completeness gates remain in the service layer. `ka_record_main_experiment` only records supplied results; `ka_claim_gate` checks completeness, not scientific validity.

## Discovery and profiles

Standard discovery returns all 24 definitions. Optional profiles are filtered views, not additional capabilities:

- `core`: research reads, user requirements, checkpoints (3 tools).
- `evidence`: core plus research memory, baseline/environment, artifacts, feedback, methods, analysis and claims.
- `formal_run`: evidence plus formal command execution.
- `execution_planning`: environment and trajectory records/queries, feedback; Codex plans the next experiment.
- `literature`: literature setup, candidates, PDF retrieval, notes and reliability.
- `paper_write`: literature plus paper recording.
- `goal`: deprecated alias for evidence; it does not control Codex goals.
- `admin`, `autonomous`, `legacy_compat`: internal/offline profiles, not registered for default MCP.
- `executor_local`: tools such as `ka_variant_create` are not registered by default; hidden unless `KVASIR_AGENT_ENABLE_EXECUTOR_MCP=1` and explicit executor environment and manifest gates pass; budget and protected-file checks still apply.

The `stage` label does not filter tool discovery. Skills are loaded by Codex when relevant. There is no all-tools/full-runtime public MCP and no custom skill search.

## Protocol example

Send this newline-delimited request to `python3 scripts/ka_mcp.py` (replace the example path):

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ka_research_read","arguments":{"project":"/absolute/research/project","operation":"resume","max_chars":6000}}}
```

Offline diagnostics remain available through `python3 scripts/doctor.py` and the internal smoke helper. Internal primitive names accepted by a local diagnostic helper are not public MCP aliases.

Responses preserve `tokens_estimate`, `chars`, `truncated`, `source_refs`, `next_call`, and `warnings`. Prefer log digests, artifact indexes and bounded resume reads over full files. See [context budget](MCP_CONTEXT_BUDGET.md) and [tool migration](TOOL_MIGRATION.md).
