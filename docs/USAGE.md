# DeepScientist Codex Native Usage

This manual tells Codex CLI how to operate DeepScientist through the native adapter. The adapter is not MCP and does not call external ds.

## Architecture

Codex loads this as a normal Codex plugin via `.codex-plugin/plugin.json`. The plugin contributes skills only. Actual DeepScientist operations are performed by `scripts/dsctl.py`, which imports `deepscientist_native.tools` and calls the curated `ds_*` handlers directly.

Runtime path semantics follow upstream `ds --here` style:

```text
<project>/DeepScientist/
```

This tree stores quests, memory, artifacts, logs, bash execution state, config, cache, and the Codex session map.

## Codex-native operation boundary

DeepScientist mode may require an action, but Codex may already have the right native operation-layer tool for the mechanical part. Use this adapter for the research **semantic layer** and use Codex-native capabilities for routine **operation-layer** work.

Codex-native operation layer:

- file read/search/edit/patch, code navigation, ordinary markdown edits, and local document cleanup;
- ordinary shell commands, dependency checks, tests, builds, lint/compile checks, and background process monitoring;
- Git/GitHub mechanics such as status, diff, branch/worktree, commit, push, PR checks, and routine CI diagnosis;
- ordinary planning, review prose, handoff drafting, and local web/PDF/arXiv retrieval before a result becomes DeepScientist evidence.

DeepScientist semantic/provenance layer:

- quest lifecycle and mode state: `ds_new_quest`, `ds_set_active_quest`, `ds_get_quest_state`, `ds_update_quest_mode`;
- durable user requirements, quest memory, artifacts, milestones, decisions, main experiment records, analysis slices, baseline gates, paper bundles, and strict-research ledgers;
- formal experiment, baseline, analysis-slice, or paper-facing commands whose logs must become quest-local evidence via `ds_bash_exec`.

Practical rule: **Codex does the mechanical action; DeepScientist records the research meaning.** If a routine Codex-native command changes the research state or supports a claim, follow it with the relevant `ds_*` memory/artifact/experiment/paper call. Use `ds_bash_exec` only when the command itself must be auditable DeepScientist provenance with a `bash_id` and `.ds/bash_exec` log.

## Start of work

1. Work from the target project root.
2. Load the `deepscientist-codex` skill.
3. Run:

```bash
python /path/to/DeepScientist-codex/scripts/dsctl.py doctor --format json
python /path/to/DeepScientist-codex/scripts/dsctl.py call ds_list_quests --format json
```

4. Select an existing quest with `ds_set_active_quest`, or create a new quest with `ds_new_quest`.
5. Load one stage skill if needed, for example `deepscientist-experiment`.
6. Persist key evidence through `ds_memory_write`, `ds_artifact_record`, or specialized tools.

## Command reference

List tools. The output is the public Codex-native canonical `ds_*` tool manifest and should report `transport="codex-native-cli"`, `mcp=false`, and the current 48-tool count. Legacy `deepscientist_*` compatibility aliases are intentionally hidden from this public manifest.

```bash
python scripts/dsctl.py list-tools --format json
```

Every public tool name is canonical `ds_*`. Historical `deepscientist_*` names are hidden legacy aliases: they may still work through `scripts/dsctl.py call <legacy_name> ...` during the compatibility window and return `deprecated_alias=true` plus `canonical_tool`, but agents should not choose them for new Codex workflows.

Show schema:

```bash
python scripts/dsctl.py schema ds_record_main_experiment --format json
```

Call a tool:

```bash
python scripts/dsctl.py call ds_get_quest_state --json '{"quest_id":"001"}' --format json
```

Shortcut form:

```bash
python scripts/dsctl.py ds_get_quest_state --arg quest_id=001 --format json
```

Project override:

```bash
python scripts/dsctl.py --project-root /path/to/project doctor --format json
```

## Important tools

- Quest control: `ds_doctor`, `ds_list_quests`, `ds_get_quest_state`, `ds_set_active_quest`, `ds_new_quest`, `ds_update_quest_mode`, `ds_events`, `ds_pause_quest`, `ds_resume_quest`, `ds_stop_quest`.
- Durable requirements: `ds_record_user_requirement`, `ds_add_user_message` with `record_only=true`.
- Memory: `ds_memory_search`, `ds_memory_read`, `ds_memory_write`, `ds_memory_list_recent`.
- Artifacts and baselines: `ds_artifact_record`, `ds_resolve_runtime_refs`, `ds_get_global_status`, `ds_get_method_scoreboard`, `ds_get_optimization_frontier`, `ds_get_conversation_context`, `ds_get_paper_contract_health`, `ds_refresh_summary`, `ds_arxiv`, `ds_create_local_baseline`, `ds_confirm_baseline`, `ds_waive_baseline`, `ds_attach_baseline`.
- Experiment/analysis: `ds_submit_idea`, `ds_record_main_experiment`, `ds_create_analysis_campaign`, `ds_get_analysis_campaign`, `ds_record_analysis_slice`, `ds_bash_exec`.
- Strict research/papers: `ds_strict_research_prepare`, `ds_strict_research_record_candidate`, `ds_strict_research_upsert_candidate`, `ds_paper_fetch`, `ds_record_literature_reading_note`, `ds_strict_research_init_bibliography`, `ds_paper_reliability_verify`, `ds_submit_paper_outline`, `ds_list_paper_outlines`, `ds_submit_paper_bundle`.

## Original Hermes MCP equivalence map

The original Hermes plugin exposed these business capabilities through MCP. In this adapter, use the Codex-native wrappers instead:

- `memory.write`, `memory.read`, `memory.search`, `memory.list_recent`: `ds_memory_write`, `ds_memory_read`, `ds_memory_search`, `ds_memory_list_recent`.
- `artifact.record`: `ds_artifact_record` or the specialized artifact tool for the workflow stage.
- `artifact.resolve_runtime_refs`: `ds_resolve_runtime_refs`.
- `artifact.get_global_status`: `ds_get_global_status`.
- `artifact.get_method_scoreboard`: `ds_get_method_scoreboard`.
- `artifact.get_optimization_frontier`: `ds_get_optimization_frontier`.
- `artifact.get_conversation_context`: `ds_get_conversation_context`.
- `artifact.get_paper_contract_health`: `ds_get_paper_contract_health`.
- `artifact.list_paper_outlines`: `ds_list_paper_outlines`.
- `artifact.refresh_summary`: `ds_refresh_summary`.
- `artifact.arxiv`: `ds_arxiv`.
- `bash_exec`: `ds_bash_exec`.

Equivalence is defined at the research workflow layer: durable quest state, memory/artifact writes, generated files, logs, status payloads, and recoverable error payloads. It intentionally does not preserve MCP protocol objects, FastMCP server behavior, MCP project config files, or MCP transport naming.

## Bundled DeepScientist support skills

The Codex adapter packages the same DeepScientist-aware support skills as the Hermes plugin. Load them by their Codex skill directory names and use `scripts/dsctl.py` for durable operations:

- `deepscientist-experiment-execution`: experiment-command execution, manifest validation, `planned_not_executed` boundaries, baseline gate/comparator handling, and `ds_bash_exec` patterns.
- `deepscientist-quest-handoffs`: `AGENTS.md`, current-status handoffs, researcher packages, sync checks, and `ds_artifact_record` milestones.
- `deepscientist-writing-plans`: implementation plans, experiment roadmaps, code-only passes, and formal command handoffs.
- `deepscientist-paper-reliability-verification`: `ds_paper_reliability_verify`, OpenReview/ACL/DBLP/Crossref evidence, and accepted-publication reliability decisions.
- `deepscientist-review`: skeptical draft/report audits, claim downgrade, revision logs, and follow-up experiment routing.

These are native Codex skills, not MCP tools. Every durable DeepScientist operation still goes through `scripts/dsctl.py call ds_* ... --format json`.

## Phase 7 control plane

Use `scripts/csctl.py` for the upgraded Codex-Scientist control plane. It emits `transport="codex-native-cli"`, is not MCP, and keeps ordinary code edits/tests in Codex-native tools.

```bash
python scripts/csctl.py manifest validate --format json
python scripts/csctl.py queue status --format json
python scripts/csctl.py summary context-pack --max-chars 12000 --format json
python scripts/csctl.py migrate legacy-quests --format json
python scripts/csctl.py soak accelerated --days 10 --inject-failures --format json
```

The `migrate legacy quests` path preserves existing `DeepScientist/quests/*` sources and writes a migration report. The `accelerated soak` path writes `DeepScientist/summaries/long_run_validation.md`; if `wall-clock soak` is still `not_run`, do not claim stable ten-day wall-clock operation.

## Safety boundaries

- no MCP transport;
- no external ds command;
- no Web UI/TUI/connectors;
- `ds_bash_exec` is reserved for quest-local evidence logging and is not a general replacement for Codex-native shell/process tools;
- keep research memory in DeepScientist state unless the user asks for another store.
