# CodexScientist Usage

CodexScientist is operated through an MCP-only default research control plane plus isolated hidden admin/debug CLI documentation for human/admin/debug/CI/recovery compatibility.

## Recommended control plane

Use MCP first for repeated research-control workflows:

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'
```

The MCP surface exposes bounded `cs_*` tools. Default `tools/list` returns the 14-tool core profile; Codex goal context uses the 47-tool goal profile filtered by active stage subset.

Use `docs/ADMIN_CLI.md` only when a human/admin/debug/CI/recovery task explicitly needs terminal compatibility commands.

## Runtime path

Runtime state lives under:

```text
<project>/CodexScientist/
```

This tree stores quests, memory, artifacts, logs, queue/runner state, config, cache, progress watchdog state, checkpoints, and summaries.

## Codex-native operation boundary

Codex-native operation layer:

- file read/search/edit/patch, code navigation, ordinary markdown edits, and local document cleanup;
- ordinary shell commands, dependency checks, tests, builds, lint/compile checks, and background process monitoring;
- Git/GitHub mechanics such as status, diff, branch/worktree, commit, push, PR checks, and routine CI diagnosis.

CodexScientist semantic/provenance layer:

- quest lifecycle and mode state;
- durable user requirements, quest memory, artifacts, milestones, decisions, main experiment records, analysis slices, baseline gates, paper bundles, strict-research ledgers, and claim gate decisions;
- progress watchdog, checkpoint/resume, method scoreboard/frontier, novelty scoring, duplicate block, related-work gate, and evidence gate state;
- formal experiment, baseline, analysis-slice, or paper-facing commands whose logs must become quest-local evidence.

Practical rule: Codex does the mechanical action; CodexScientist records the research meaning.

## Goal context flow

`/goal` is Codex-native. CodexScientist does not implement slash commands. After Codex has entered goal context, use:

1. `cs_new_quest` and `cs_record_user_requirement` to anchor the task;
2. `cs_goal_context` to read `allowed_tools_for_stage`;
3. baseline/idea/experiment/analysis tools for the active stage;
4. `cs_goal_watchdog` during long-running work;
5. `cs_checkpoint` at stage boundaries;
6. `cs_resume_brief` and `cs_pack_delta` after context compaction or interruption.

## Skill retrieval and context budget

Do not reread long skill files by default. Use:

- `cs_skill_search` to get short skill cards.
- `cs_skill_load` to load a bounded `preview`, `runtime`, `risk`, `sections`, or explicitly allowed `full` view.

Long-task recovery should normally use `cs_status` plus `cs_resume_brief` in the 4K-8K range. Use `cs_pack_delta` for post-checkpoint changes, `cs_log_digest` before raw logs, `cs_artifact_index` before opening artifacts, `cs_goal_watchdog` before assuming a runner is healthy, and `cs_checkpoint` at stage boundaries. Context budget is not smaller is better; incident/debug/audit work may expand to 12K-24K while still avoiding raw full logs and full artifact content unless explicitly requested.

## Default autonomy

The default mode is `copilot`. Automatic idea or novelty improvement requires an explicit user request or an explicit manifest/handoff requirement.

## Safety boundaries

- Use only curated `cs_*` MCP tools in the default MCP path.
- Keep hidden admin/debug CLI available but isolated from the default agent-facing research path.
- Avoid all-tools/full-runtime MCP registration.
- Keep large logs, ledgers, papers, and reference repositories out of context unless an explicit bounded raw read is needed.
- Use `cs_bash_exec` only when the command itself must be auditable CodexScientist provenance, not as a general shell replacement.

## Long-run claims

Accelerated soak and fake-clock validation do not prove real overnight or ten-day wall-clock stability. If real wall-clock soak has not been run, report it as `not_run`.
