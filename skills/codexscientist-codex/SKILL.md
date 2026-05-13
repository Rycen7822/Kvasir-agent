---
name: codexscientist-codex
description: Low-token router for CodexScientist in Codex CLI. MCP-only default for research-control workflows after Codex has entered ordinary or goal context.
---

# CodexScientist Codex Router

This skill is a thin router. It states policy and boundaries; it is not a full command manual.

## Core rules

- MCP-only default: use the curated `cs_*` MCP surface for repeated research-control workflows.
- `/goal` is Codex-native. CodexScientist does not implement slash commands; after Codex has entered goal context, this router maps research semantics to MCP calls, project-local state, checkpoint, and resume contracts.
- Start from the visible MCP surface: inspect `tools/list`, then call `cs_tool_schema` for the one tool you intend to use.
- Runtime state lives in `<project>/CodexScientist/`.
- Persist durable research facts through `cs_*` calls when they affect quest state, memory, artifacts, baselines, experiments, reviews, analysis, method improvement, or evidence.
- For long-task recovery, call `cs_status` then `cs_resume_brief` with the default 4K-8K budget; use `cs_pack_delta` only when changes after a checkpoint are too large for the brief.
- Use `cs_log_digest` before reading raw logs, and `cs_artifact_index` before opening artifact files.
- End each completed stage with `cs_checkpoint` so later turns can resume without chat history.
- Load bundled Codex plugin support skills only through the Codex-native skill mechanism, and only when the current subtask actually needs one.

## Default autonomy mode

The default mode is `copilot`.

In copilot mode, CodexScientist records, checks, organizes, retrieves, and summarizes research state. It may check novelty or duplicate risk for a user-provided or document-provided idea, but it must not own the research direction.

`autonomous_idea_improvement` is disabled by default. Enable it only when the user explicitly asks for automatic idea/novelty improvement, or when a project manifest or handoff explicitly requires autonomous idea improvement. Otherwise, do not invent or improve ideas automatically; output candidate plans for user review instead of creating new running trials.

## Operation boundary

Codex-native operation layer:

- routine file, shell, Git, test, build, and process work;
- file read/search/edit/patch and code navigation;
- ordinary dependency checks, lint, smoke tests, commits, diffs, and process monitoring.

CodexScientist semantic/provenance layer:

- quest lifecycle and mode state;
- durable user requirements, memory, artifacts, milestones, decisions, baselines, experiment records, analysis slices, method improvement gates, and paper/reliability ledgers;
- formal evidence commands whose logs must be quest-local evidence.

Codex does the mechanical action; CodexScientist records the research meaning. Use `cs_bash_exec` only when the command itself must be auditable CodexScientist provenance, not as a general shell replacement.

## Start of work

From the target project root, initialize and inspect the MCP surface with CodexScientist MCP smoke helpers or direct MCP `initialize` / `tools/list`. Then follow this MCP-first flow:

1. Call `cs_status` or `cs_doctor`.
2. If no quest exists for this task, call `cs_new_quest`.
3. Record stable user constraints with `cs_record_user_requirement`.
4. Choose the explicit profile that matches the work: `evidence`, `formal_run`, `literature`, or `paper_write`.
5. Call `cs_tool_schema` for the selected tool before using it when arguments are not obvious.
6. Use only tools visible in the current profile for status, manifest, context pack, durable research state, evidence, literature, paper, or recovery.
7. If MCP is unavailable, fail closed in the default agent path: run diagnostics and repair MCP configuration instead of switching the research workflow to an admin/debug path.

## Output policy

Prefer compact status, bounded log tails, artifact paths, hashes, and summaries. Do not inject full logs, full JSONL ledgers, full papers, or full reference repositories into Codex context unless an explicit raw/range read is required. Full support-skill text and raw artifact content are explicit opt-in paths, not defaults.

## Final reply checklist

Report:

- quest id and stage if used;
- MCP tools used;
- files created or modified;
- new or updated durable memory/artifacts;
- verification results;
- next action or user-gated decision.
