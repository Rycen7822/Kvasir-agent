# Public tool migration

The public MCP API now contains 24 tools. Existing project records are preserved. Internal handlers and offline diagnostics are not compatibility aliases on MCP.

Every public call requires an absolute `project`; omit `project_root` and `quest_id`. Quest provenance is derived from the project manifest. Start a new Codex thread after updating.

## Consolidated operations

| Previous tool | Public tool | operation |
|---|---|---|
| `ka_status` | `ka_research_read` | `status` |
| `ka_resume_brief` | `ka_research_read` | `resume` |
| `ka_pack_delta` | `ka_research_read` | `delta` |
| `ka_review_status` | `ka_research_read` | `review` |
| `ka_memory_search` | `ka_memory_query` | `search` |
| `ka_memory_read` | `ka_memory_query` | `read` |
| `ka_memory_list_recent` | `ka_memory_query` | `recent` |
| `ka_create_local_baseline` | `ka_baseline` | `create` |
| `ka_confirm_baseline` | `ka_baseline` | `confirm` |
| `ka_manifest_record_baseline` | `ka_baseline` | `record` |
| `ka_environment_register` | `ka_environment` | `register` |
| `ka_environment_validate` | `ka_environment` | `validate` |
| `ka_environment_show` | `ka_environment` | `show` |
| `ka_manifest_validate` | `ka_environment` | `validate_manifest` |
| `ka_trajectory_search` | `ka_trajectory_query` | `search` |
| `ka_trajectory_show` | `ka_trajectory_query` | `show` |
| `ka_submit_idea` | `ka_method_record` | `idea` |
| `ka_record_negative_result` | `ka_method_record` | `negative` |
| `ka_update_method_scoreboard` | `ka_method_record` | `result` |
| `ka_create_analysis_campaign` | `ka_analysis` | `create` |
| `ka_get_analysis_campaign` | `ka_analysis` | `read` |
| `ka_record_analysis_slice` | `ka_analysis` | `record_slice` |
| `ka_strict_research_prepare` | `ka_literature_setup` | `prepare` |
| `ka_strict_research_init_bibliography` | `ka_literature_setup` | `bibliography` |
| `ka_submit_paper_outline` | `ka_paper_record` | `outline` |
| `ka_submit_paper_bundle` | `ka_paper_record` | `bundle` |

`ka_research_read(operation="methods")` reads the persisted scoreboard and frontier; it replaces the old placeholder query tools without changing files.

## Removed default entries

| Previous tool | Replacement |
|---|---|
| `ka_tool_schema` | Read the schema already returned by standard tool discovery. |
| `ka_doctor` | Offline `python3 scripts/doctor.py`. |
| `ka_refresh_summary` | Codex file editing based on evidence; the internal old call also refuses template overwrite. |
| `ka_get_method_scoreboard`, `ka_get_optimization_frontier` | `ka_research_read` with `operation="methods"`. |
| `ka_arxiv` | Read the project arXiv library file; use `ka_paper_fetch` for downloads. |
| `ka_evolutionary_plan_round` | Codex experiment planning; deterministic internal planner remains available offline. |
| `ka_strict_research_record_candidate` | `ka_strict_research_upsert_candidate`; repeated identity updates one row instead of appending duplicates. |

## Independent tools

These retain their names but use the canonical public project parameter:

`ka_record_user_requirement`, `ka_checkpoint`, `ka_memory_write`, `ka_artifact_record`, `ka_artifact_index`, `ka_bash_exec`, `ka_log_digest`, `ka_trajectory_record`, `ka_feedback_ingest`, `ka_record_main_experiment`, `ka_claim_gate`, `ka_strict_research_upsert_candidate`, `ka_record_literature_reading_note`, `ka_paper_fetch`, `ka_paper_reliability_verify`.

## Validation and permissions

Each operation validates its own typed fields before service calls. Domain guards still validate baseline/evaluator protection, novelty inputs, formal command provenance, feedback metrics and claim material. Mixed read/write tools are marked writable; query tools are marked read-only. Baseline readiness recording remains distinct from baseline confirmation. Tool availability does not authorize an experiment.

Old files and their quest ids are preserved. Archived playbooks describe historical API names; apply this mapping when using their research guidance.
