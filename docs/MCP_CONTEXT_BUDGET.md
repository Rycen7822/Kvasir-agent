# MCP Context Budget

CodexScientist context budgeting is for stable long-task recovery, not aggressive minimization. The rule is not smaller is better: a recovery package that is too small can lose goals, constraints, validation state, risks, and source references.

## Default budget ranges

| Scenario | Default | May expand to | Required anchors |
| --- | ---: | ---: | --- |
| Normal resume | 4K-8K chars | 12K chars | quest, constraints, autonomy mode, last checkpoint, validation, risks, source_refs |
| Incident/debug/audit | 8K chars | 12K-24K chars | error class, bounded log digest, artifact refs, decisions, changed events |
| Raw/range inspection | explicit only | explicit only | reason, path, bounded range, follow-up checkpoint |

Do not compress normal recovery into a few hundred characters. Use a bounded structured brief first, then request deltas or specific ranges only when needed.

## Default recovery flow

1. Call `cs_status` for project and state-root sanity.
2. Call `cs_resume_brief` with `max_chars` in the 4K-8K range.
3. If a prior checkpoint exists and many events changed, call `cs_pack_delta` from that event sequence or checkpoint id.
4. Inspect long logs through `cs_log_digest` before any bounded raw tail.
5. Inspect artifacts through `cs_artifact_index` before opening artifact files.
6. Use public recovery payloads from `cs_status`, `cs_resume_brief`, and `cs_pack_delta` for runner/heartbeat/stuck-state questions; hidden/admin-only watchdog diagnostics stay outside the default MCP surface.
7. Finish each phase with `cs_checkpoint` so the next turn can recover without chat history.

## Current MCP profiles

The default core profile has 11 tools. Wider agent-facing profiles are explicit: `evidence`, `formal_run`, `literature`, and `paper_write`. The `goal` profile is a deprecated compatibility alias for `evidence`.

Important current tools include:

```text
cs_doctor
cs_status
cs_tool_schema
cs_new_quest
cs_record_user_requirement
cs_context_pack
cs_resume_brief
cs_checkpoint
cs_pack_delta
cs_manifest_validate
cs_create_local_baseline
cs_confirm_baseline
cs_submit_idea
cs_record_main_experiment
cs_create_analysis_campaign
cs_record_analysis_slice
cs_log_digest
cs_artifact_index
cs_claim_gate
```

## Explicit opt-in paths

- Raw logs are not default context. Use `cs_log_digest` first; read raw logs only with an explicit bounded range and reason.
- Full artifact content is not default context. Use `cs_artifact_index` first; open a full artifact only when the current task explicitly requires it.
- Full papers, full JSONL ledgers, full reference repositories, and full support-skill files are never part of the default resume path.
- Bundled support skills are loaded through Codex plugin skill routing when needed; they are not part of the default profile.

## Selective schema and bounded support loading

`cs_tool_schema` returns detailed native schemas when available and a minimal registry schema for registry-only tools. Unsupported names fail closed with `unknown_tool`.

These constraints preserve the no all-tools/full-runtime MCP boundary: lightweight tool cards, selective schemas, bounded skills, log digests, artifact indexes, checkpoints, and resume briefs are the default recovery mechanism.

## Envelope expectations

Every curated MCP response should preserve a budget envelope with `tokens_estimate`, `chars`, `truncated`, `source_refs`, `warnings`, and actionable suggested next calls when another tool call is the expected continuation.

## Boundary reminder

Codex handles normal file, shell, git, test, build, and process work. CodexScientist handles research semantics, provenance, runner/queue state, context packs, manual diagnostics, checkpoints, log digests, artifact indexes, claim gates, and evidence ledgers. Keep the MCP curated; do not expose an all-tools/full-runtime MCP.
