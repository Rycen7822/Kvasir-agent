# MCP Context Budget

Kvasir-agent context budgeting is for stable long-task recovery, not aggressive minimization. The rule is not smaller is better: a recovery package that is too small can lose goals, constraints, validation state, risks, and source references.

## Default budget ranges

| Scenario | Default | May expand to | Required anchors |
| --- | ---: | ---: | --- |
| Normal resume | 4K-8K chars | 12K chars | research state, constraints, autonomy mode, last checkpoint, validation, risks, source_refs |
| Incident/debug/audit | 8K chars | 12K-24K chars | error class, bounded log digest, artifact refs, decisions, changed events |
| Raw/range inspection | explicit only | explicit only | reason, path, bounded range, follow-up checkpoint |

Do not compress normal recovery into a few hundred characters. Use a bounded structured brief first, then request deltas or specific ranges only when needed.

## Default recovery flow

1. Call `ka_research_read(operation="status")` for project and state-root sanity.
2. Call `ka_research_read(operation="resume")` with `max_chars` in the 4K-8K range.
3. If a prior checkpoint exists and many events changed, call `ka_research_read(operation="delta")` from that event sequence or checkpoint id.
4. Inspect long logs through `ka_log_digest` before any bounded raw tail.
5. Inspect artifacts through `ka_artifact_index` before opening artifact files.
6. Use public recovery payloads from `ka_research_read(operation="status")`, `ka_research_read(operation="resume")`, and `ka_research_read(operation="delta")` for runner/heartbeat/stuck-state questions; hidden/admin-only watchdog diagnostics stay outside the default MCP surface.
7. Finish each phase with `ka_checkpoint` so the next turn can recover without chat history.

## Current MCP profiles

Standard discovery advertises all 24 public research tools with parameter schemas. Profiles such as `core`, `evidence`, `formal_run`, `literature`, and `paper_write` optionally filter this catalog. The `goal` profile is a deprecated compatibility alias for `evidence`.

Core contains `ka_research_read`, `ka_record_user_requirement`, and `ka_checkpoint`. Other workflows use the domain tools listed in [MCP](MCP.md).

Every public call requires an absolute `project`. Domain operations have typed schemas and operation-specific required arguments. Project aliases and caller-supplied quest ids are absent from the public API.

## Explicit opt-in paths

- Raw logs are not default context. Use `ka_log_digest` first; read raw logs only with an explicit bounded range and reason.
- Full artifact content is not default context. Use `ka_artifact_index` first; open a full artifact only when the current task explicitly requires it.
- Full papers, full JSONL ledgers, full reference repositories, and full support-skill files are never part of the default resume path.
- Bundled support skills are loaded through Codex plugin skill routing when needed; they are not part of the default profile.

## Definition budget

The 24-tool catalog is about 6.0K o200k_base tokens before host-added metadata. This measures compact function definitions, not actual per-turn model usage. Discovery and model loading are distinct; tool results, loaded skills and research content consume additional context. Keep result bounds even when aggregating queries.

## Envelope expectations

Every curated MCP response should preserve a budget envelope with `tokens_estimate`, `chars`, `truncated`, `source_refs`, `warnings`, and actionable suggested next calls when another tool call is the expected continuation.

## Boundary reminder

Codex handles normal file, shell, git, test, build, and process work. Kvasir-agent handles research semantics, provenance, runner/queue evidence, manual diagnostics, checkpoints, log digests, artifact indexes, claim gates, and evidence ledgers. Keep the MCP curated; do not expose an all-tools/full-runtime MCP.
