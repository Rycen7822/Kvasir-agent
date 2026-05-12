# MCP Context Budget

CodexScientist context budgeting is for stable long-task recovery, not aggressive minimization. The rule is not smaller is better: a recovery package that is too small can lose goals, constraints, validation state, and next action anchors.

## Default budget ranges

| Scenario | Default | May expand to | Required anchors |
| --- | ---: | ---: | --- |
| Normal resume | 4K-8K chars | 12K chars | goal, constraints, autonomy mode, last checkpoint, next_action, validation, risks, source_refs |
| Incident/debug/audit | 8K chars | 12K-24K chars | error class, bounded log digest, artifact refs, decisions, changed events |
| Raw/range inspection | explicit only | explicit only | reason, path, bounded range, follow-up checkpoint |

Do not compress normal recovery into a few hundred characters. Use a bounded structured brief first, then request deltas or specific ranges only when needed.

## Default recovery flow

1. Call `cs_status` for project and state-root sanity.
2. Call `cs_goal_context` to get the active stage and `allowed_tools_for_stage`.
3. Call `cs_resume_brief` with `max_chars` in the 4K-8K range.
4. If a prior checkpoint exists and many events changed, call `cs_pack_delta` from that event sequence or checkpoint id.
5. Load at most one skill with `cs_skill_search` then `cs_skill_load(view="preview"|"runtime")` when a procedure is needed.
6. Inspect long logs through `cs_log_digest` before any bounded raw tail.
7. Inspect artifacts through `cs_artifact_index` before opening artifact files.
8. Use `cs_goal_watchdog` to reconcile stuck runners and checkpoint pressure.
9. Finish each stage with `cs_checkpoint` so the next turn can recover without chat history.

## Current MCP profiles

The default core profile has 14 tools. The goal profile has 47 tools and is filtered by active stage subset after Codex has entered `/goal` context.

Important current tools include:

```text
cs_doctor
cs_status
cs_goal_context
cs_goal_state
cs_goal_next_action
cs_tool_schema
cs_context_pack
cs_resume_brief
cs_checkpoint
cs_pack_delta
cs_skill_search
cs_skill_load
cs_manifest_validate
cs_trial_show
cs_runner_status
cs_log_digest
cs_artifact_index
cs_queue_status
cs_goal_watchdog
cs_update_method_scoreboard
cs_select_next_idea
cs_claim_gate
```

## Explicit opt-in paths

- `cs_skill_load(view="full")` requires `allow_full=true` and a bounded `max_chars` value.
- Raw logs are not default context. Use `cs_log_digest` first; read raw logs only with an explicit bounded range and reason.
- Full artifact content is not default context. Use `cs_artifact_index` first; open a full artifact only when the current task explicitly requires it.
- Full papers, full JSONL ledgers, full reference repositories, and full skill files are never part of the default resume path.

## Selective schema and bounded skill loading

`cs_tool_schema` is a selective lazy full-schema endpoint. It is intentionally not a full registry catalog; unsupported names fail closed with `unknown_tool` even when the tool exists in `tools/list` as a compact card.

`cs_skill_search` returns short cards and `cs_skill_load` returns bounded preview/runtime views by default. Agent-facing skill loads should not expose terminal compatibility command guidance. Full skill text remains explicit opt-in only through `view="full"`, `allow_full=true`, and a bounded `max_chars`.

These constraints preserve the no all-tools/full-runtime MCP boundary: stage subsets, lightweight tool cards, selective schemas, bounded skills, log digests, artifact indexes, checkpoints, and resume briefs are the default recovery mechanism.

## Envelope expectations

Every curated MCP response should preserve a budget envelope with `tokens_estimate`, `chars`, `truncated`, `source_refs`, `warnings`, and actionable `next_call` / `next_action` style guidance when another tool call is the expected continuation.

## Boundary reminder

Codex handles normal file, shell, git, test, build, and process work. CodexScientist handles research semantics, provenance, runner/queue state, context packs, progress watchdog, checkpoints, log digests, artifact indexes, claim gates, and evidence ledgers. Keep the MCP curated; do not expose an all-tools/full-runtime MCP.
