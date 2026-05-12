# CodexScientist MCP

CodexScientist provides a stable curated MCP control plane for repeated research-control workflows.

## Goals

- Reduce repeated long-skill reads.
- Expose a small stable `cs_*` tool family.
- Keep CLI fallback for CI, debugging, migration, recovery, and MCP-unavailable environments.
- Reuse `codex_scientist/services` rather than shelling out to `scripts/csctl.py` as the main implementation.

## Smoke commands

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'
python scripts/cs_mcp.py --stdio-smoke call cs_manifest_validate '{"project":"/path/to/project"}'
```

## Current curated tool families

The default curated surface currently has 20 tools:

- Core: `cs_doctor`, `cs_status`.
- Context/recovery: `cs_context_pack`, `cs_resume_brief`, `cs_checkpoint`, `cs_pack_delta`.
- Manifest/trial: `cs_manifest_validate`, `cs_trial_show`.
- Runner/queue: `cs_runner_status`, `cs_log_digest`, `cs_artifact_index`, `cs_queue_status`, `cs_queue_reconcile`.
- Wiki/review/cost: `cs_wiki_query_pack`, `cs_review_status`, `cs_cost_status`.
- Soak: `cs_soak_accelerated`, `cs_soak_crash_resume`.
- Skill retrieval: `cs_skill_search`, `cs_skill_load`.

## Skill retrieval

`cs_skill_search` returns short cards only. `cs_skill_load` loads bounded views and rejects forged handles, path traversal, unknown ids, and full-view loads without explicit `allow_full=true`.

## Safety

- No all-tools/full-runtime MCP.
- Tool annotations expose read-only/destructive/idempotent/open-world hints.
- Outputs must be bounded and redacted.
- Errors return `ok=false`, `error_type`, `recoverable`, and a suggested next action when useful.
