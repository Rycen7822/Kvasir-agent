# CodexScientist Usage

CodexScientist is operated through an MCP-only default research control plane. Hidden admin/debug/native CLI paths remain available only for explicit human, CI, recovery, or compatibility work.

## Recommended control plane

Use MCP first for repeated research-control workflows:

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'
```

The default core profile exposes 11 curated `cs_*` tools for status, quest anchoring, passive context/recovery anchors, checkpointing, and schema lookup. Wider agent-facing profiles are explicit:

- `evidence`: 31 tools for quest-local evidence, memory, manifest, baseline, artifact, experiment, analysis, and method ledgers.
- `formal_run`: 32 tools; `evidence` plus formal `cs_bash_exec` provenance-gated execution.
- `literature`: 23 tools for strict literature and quest-local paper resources.
- `paper_write`: 27 tools for literature plus paper outline/bundle/summary/review work.

The goal profile is deprecated; use `evidence` unless you are explicitly testing legacy compatibility. The stage is a label for context and records; it is not used to filter `tools/list` output.

Use `docs/ADMIN_CLI.md` only when a human/admin/debug/CI/recovery task explicitly needs terminal compatibility commands.

## Runtime path

Runtime state lives under:

```text
<project>/CodexScientist/
```

For MCP calls, pass `project` as the preferred project root argument. `project_root` is accepted as a compatibility alias. Both should resolve to the same runtime path.

This tree stores quests, quest-local memory, artifacts, logs, queue/runner state, config, cache, passive checkpoints, recovery anchors, summaries, and manual watchdog diagnostic records (manual progress watchdog diagnostics; no default watchdog state writes).

## Codex-native operation boundary

Codex-native operation layer:

- file read/search/edit/patch, code navigation, ordinary markdown edits, and local document cleanup;
- ordinary shell commands, dependency checks, tests, builds, lint/compile checks, and background process monitoring;
- Git/GitHub mechanics such as status, diff, branch/worktree, commit, push, PR checks, and routine CI diagnosis.

CodexScientist semantic/provenance layer:

- quest lifecycle and mode state;
- durable user requirements, quest-local memory, artifacts, milestones, decisions, main experiment records, analysis slices, baseline gates, paper bundles, strict-research ledgers, and claim gate decisions;
- manual watchdog diagnostic snapshots, passive checkpoint/resume anchors, method scoreboard/frontier, novelty scoring, duplicate block, related-work gate, and evidence gate state;
- formal experiment, baseline, analysis-slice, or paper-facing commands whose logs must become quest-local evidence.

Practical rule: Codex does the mechanical action; CodexScientist records the research meaning.

## Codex-native `/goal` boundary

`/goal` is Codex-native. CodexScientist does not implement slash commands and does not act as the planner.

Recommended flow after Codex has entered goal context:

1. `cs_new_quest` and `cs_record_user_requirement` anchor the task.
2. Choose an explicit MCP profile for the current evidence surface, usually `evidence`, `formal_run`, `literature`, or `paper_write`.
3. Use baseline, idea, experiment, analysis, literature, or paper tools to record research evidence and gates.
4. Use `cs_goal_watchdog` only as a manual watchdog diagnostic during long-running work.
5. Use `cs_checkpoint` at phase boundaries.
6. Use `cs_resume_brief` and `cs_pack_delta` after context compaction or interruption.

## Schema, skills, and context budget

`cs_tool_schema` returns detailed native schemas when available and a minimal registry schema for MCP registry-only tools. Every tool returned by `tools/list` should at least expose required arguments through either `tools/list` or `cs_tool_schema`.

Skill retrieval helpers (`cs_skill_search`, `cs_skill_load`) are hidden/direct tools rather than default profile tools. They may be called only by explicit compatibility or debugging flows that already know the tool names; they are not part of the default Codex-facing control plane.

Long-task recovery should normally use `cs_status` plus `cs_resume_brief` in the 4K-8K range. Use `cs_pack_delta` for post-checkpoint changes, `cs_log_digest` before raw logs, `cs_artifact_index` before opening artifacts, and `cs_checkpoint` at phase boundaries. Context budget is not smaller is better; incident/debug/audit work may expand to 12K-24K while still avoiding raw full logs and full artifact content unless explicitly requested.

## Native CLI boundary

The native CLI is not the default control plane. It exists for human/admin/debug/CI/recovery compatibility.

`cs_status` is available in the native CLI as a lightweight boundary hint, but MCP registry-only tools should normally be exercised through `scripts/cs_mcp.py`.

Legacy `codexscientist_*` aliases are disabled by default. Use canonical `cs_*` names and prefer MCP for agent-facing research-control work.

## Default autonomy

The default mode is `copilot`. Automatic idea or novelty improvement requires an explicit user request or an explicit manifest/handoff requirement.

## Safety boundaries

- Use only curated `cs_*` MCP tools in the default MCP path.
- Keep hidden admin/debug CLI available but isolated from the default agent-facing research path.
- Avoid all-tools/full-runtime MCP registration.
- Keep large logs, ledgers, papers, and reference repositories out of context unless an explicit bounded raw read is needed.
- Use `cs_bash_exec` only when the command itself must be auditable CodexScientist provenance, not as a general shell replacement.
- Use `dry_run=true` or `network=false` for open-world literature checks when Codex needs a bounded planning response instead of external IO.

## Long-run claims

Accelerated admin-only stability validation does not prove real overnight or ten-day wall-clock stability. If real wall-clock validation has not been run, report it as `not_run`.
