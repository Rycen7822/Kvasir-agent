# CodexScientist Usage

CodexScientist is operated through a stable curated MCP control plane plus a CLI fallback.

## Recommended control plane

Use MCP first for repeated research-control workflows:

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'
```

The curated MCP exposes bounded `cs_*` tools, including doctor/status, resume/checkpoint/delta, manifest validation, runner/queue status, log digest, artifact index, context pack, and skill retrieval. It is intentionally smaller than the full native runtime.

Use CLI fallback when MCP is unavailable, when CI needs a plain command, or when debugging/recovery/migration requires terminal output:

```bash
python scripts/csctl.py doctor --format json
python scripts/csctl.py list-tools --format json
python scripts/csctl.py manifest validate --format json
python scripts/csctl.py queue status --format json
```

## Runtime path

Runtime state lives under:

```text
<project>/CodexScientist/
```

This tree stores quests, memory, artifacts, logs, queue/runner state, config, cache, and summaries.

## Codex-native operation boundary

Codex-native operation layer:

- file read/search/edit/patch, code navigation, ordinary markdown edits, and local document cleanup;
- ordinary shell commands, dependency checks, tests, builds, lint/compile checks, and background process monitoring;
- Git/GitHub mechanics such as status, diff, branch/worktree, commit, push, PR checks, and routine CI diagnosis.

CodexScientist semantic/provenance layer:

- quest lifecycle and mode state;
- durable user requirements, quest memory, artifacts, milestones, decisions, main experiment records, analysis slices, baseline gates, paper bundles, and strict-research ledgers;
- formal experiment, baseline, analysis-slice, or paper-facing commands whose logs must become quest-local evidence.

Practical rule: Codex does the mechanical action; CodexScientist records the research meaning.

## Skill retrieval and context budget

Do not reread long skill files by default. Use:

- `cs_skill_search` to get short skill cards.
- `cs_skill_load` to load a bounded `preview`, `runtime`, `risk`, `sections`, or explicitly allowed `full` view.

Long-task recovery should normally use `cs_status` plus `cs_resume_brief` in the 4K-8K range. Use `cs_pack_delta` for post-checkpoint changes, `cs_log_digest` before raw logs, `cs_artifact_index` before opening artifacts, and `cs_checkpoint` at stage boundaries. Context budget is not smaller is better; incident/debug/audit work may expand to 12K-24K while still avoiding raw full logs and full artifact content unless explicitly requested.

## Default autonomy

The default mode is `copilot`. Automatic idea or novelty improvement requires an explicit user request or an explicit manifest/handoff requirement.

## Safety boundaries

- Use only curated `cs_*` MCP tools in the default MCP path.
- Keep CLI fallback available but do not use it as the primary MCP implementation.
- Avoid all-tools/full-runtime MCP registration.
- Keep large logs, ledgers, papers, and reference repositories out of context unless an explicit bounded raw read is needed.
- Use `cs_bash_exec` only when the command itself must be auditable CodexScientist provenance.

## Long-run claims

Accelerated soak and fake-clock validation do not prove real overnight or ten-day wall-clock stability. If real wall-clock soak has not been run, report it as `not_run`.
