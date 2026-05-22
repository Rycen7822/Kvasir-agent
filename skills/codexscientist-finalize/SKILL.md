---
name: codexscientist-finalize
description: Compact Codex-Scientist router for codexscientist-finalize; use for its research stage while keeping Codex-native operations outside the plugin runtime.
version: 2.0.0
---

# codexscientist-finalize compact router

This active skill is intentionally compact. The historical long playbook was moved to `references/legacy-playbook.md` and is reference-only.

## Operating contract

- Codex-Scientist is a Codex CLI plugin, not a standalone autonomous framework.
- Default mode is `copilot`; do not invent, improve, or expand ideas automatically unless the user or project manifest explicitly enables autonomous idea improvement.
- Use Codex-native file search, edits, shell, tests, and git for ordinary development work.
- Use MCP `cs_*` tools only when visible in the selected profile; prefer public families for root-bound research state, memory, artifacts, baselines, experiments, analysis, literature, paper, method/frontier, claim gates, checkpoint/resume, and compact evidence.
- Keep outputs compact. Return paths, ids, hashes, metric values, short tails, and next action; do not paste full logs, full background notes, or full historical playbooks into context.
- Do not execute old API names directly. Translate historical playbook wording to current MCP `cs_*` tool calls.

## Current MCP tool surface

Use the relevant bounded MCP `cs_*` tools exposed by `tools/list` and `cs_tool_schema` for this stage. Hidden admin/debug CLI examples live only in `docs/ADMIN_CLI.md`.

## Stage workflow

1. Read `CodexScientist/research.yaml` and `CodexScientist/summaries/context_pack.md` when present.
2. Identify the single next bounded research action for this stage.
3. If stage-specific nuance is needed, read only the relevant section of `references/legacy-playbook.md` and translate it to the current MCP `cs_*` tool surface.
4. Apply manifest, baseline, metric, readonly, budget, and autonomy gates before any experiment/run changes.
5. Record durable outcomes through MCP `cs_*` tools and keep ordinary code edits in Codex-native operations.

## Legacy reference

`references/legacy-playbook.md` preserves the pre-upgrade detailed playbook for audit and migration. It may contain old names and long procedures. Treat it as source material, not executable instructions.
