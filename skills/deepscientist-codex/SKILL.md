---
name: deepscientist-codex
description: Low-token router for using DeepScientist from Codex CLI through the native dsctl/csctl adapter. Use it for research semantics and provenance; keep routine coding work Codex-native. Not MCP.
---

# DeepScientist Codex Native

This skill is the low-token router for the native Codex plugin. It states policy, boundaries, and when to call the local control script; it is not a full tool manual.

## Core rules

- Use `scripts/csctl.py` as the primary native control surface; `scripts/dsctl.py` remains a compatibility alias.
- Do not use MCP for this plugin. There is no `.mcp.json`, no server-transport registry entry, and no external npm `ds` call for normal operation.
- Runtime state lives in `<project>/DeepScientist/` when operating from a research project root.
- Persist durable research facts through native `ds_*` calls when they affect quest state, memory, artifacts, baselines, experiments, reviews, or evidence.
- Load this skill first; load at most one stage/support skill when the current subtask actually needs it.

## Default autonomy mode

The default mode is `copilot`.

In copilot mode, DeepScientist records, checks, organizes, retrieves, and summarizes research state. It may check novelty or duplicate risk for a user-provided or document-provided idea, but it must not own the research direction.

`autonomous_idea_improvement` is disabled by default. Enable it only when the user explicitly asks for automatic idea/novelty improvement, or when a project manifest or handoff explicitly requires autonomous idea improvement. Otherwise, do not invent or improve ideas automatically; output candidate plans for user review instead of creating new running trials.

## Codex-native operation boundary

Codex-native operation layer:

- routine file, shell, Git, test, build, and process work;
- file read/search/edit/patch and code navigation;
- ordinary dependency checks, lint, smoke tests, commits, diffs, and process monitoring.

DeepScientist semantic/provenance layer:

- quest lifecycle and mode state;
- durable user requirements, memory, artifacts, milestones, decisions, baselines, experiment records, analysis slices, and paper/reliability ledgers;
- formal evidence commands whose logs must be quest-local evidence.

Codex does the mechanical action; DeepScientist records the research meaning. Use `ds_bash_exec` only when the command itself must be auditable DeepScientist provenance, not as a general shell replacement.

## Start of work

From the target project root:

```bash
python /path/to/DeepScientist-codex/scripts/csctl.py doctor --format json
python /path/to/DeepScientist-codex/scripts/csctl.py list-tools --format json
```

If no relevant quest exists, create one in copilot mode unless explicit instructions require autonomous mode:

```bash
python /path/to/DeepScientist-codex/scripts/csctl.py call ds_new_quest --json '{"goal":"...","title":"...","workspace_mode":"copilot"}' --format json
```

## Tool routing

Use the native control script for durable semantic actions: quest status, durable requirements, memory search/write, artifact records, baseline gates, formal experiment records, analysis state, paper/reliability ledgers, event reads, and compact summaries.

Use ordinary Codex-native tools for mechanical edits and checks. If a mechanical result supports a research claim or changes quest state, follow it with the appropriate durable record.

## Output policy

Prefer compact status, bounded log tails, artifact paths, hashes, and summaries. Do not inject full logs, full JSONL ledgers, full papers, or full reference repositories into Codex context unless an explicit raw/range read is required.

## Final reply checklist

Report:

- quest id and stage if used;
- control commands or native tool classes used;
- files created or modified;
- new or updated durable memory/artifacts;
- verification results;
- next action or user-gated decision.
