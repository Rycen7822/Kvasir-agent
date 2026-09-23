---
name: kvasir-agent
description: Maintain durable research evidence, constraints and recovery state with Kvasir-agent while Codex manages the task and ordinary coding work.
---

# Kvasir-agent research workspace

Use the `ka_*` MCP tools for research records under `<project>/Kvasir-agent/`. Codex owns `/goal`, continuation, native skill discovery, file editing, shell, Git, tests and ordinary process management.

## Start or resume

1. Pass the absolute target project root as `project` on each research MCP call. The bundled server launches from the plugin cache. The server derives `quest_id` from that project manifest; do not pass `quest_id` or `project_root`.
2. Call `ka_research_read(operation="status")`, then `ka_research_read(operation="resume")` for checkpoint, evidence and risk anchors. Inspect referenced artifacts only as needed. Use `ka_research_read(operation="delta")` for changes since a known checkpoint.
3. Record durable user constraints with `ka_record_user_requirement`; the first write initializes project state. Read-only status does not create a new research project.
4. Use the tools already advertised by MCP with their parameter schemas. Explicit profiles are optional diagnostic filters.
5. Save a `ka_checkpoint` at meaningful milestones or before handoff, including completed work, decisions, actual validation, risks and the next action.

## Choose a research workflow

Load through Codex's native skill mechanism only when relevant:

- **kvasir-agent-experiment**: baseline, novelty inputs, measured results, negative memory and analysis.
- **kvasir-agent-strict-research**: literature qualification and bibliography.
- **ka-paper-reliability**: paper identity, acceptance and evidence cards.
- **kvasir-agent-write**: evidence-backed drafting, review and paper bundles.
- **kvasir-agent-figure-polish**: render and inspect research figures.
- **kvasir-agent-quest-handoffs**: researcher handoffs and durable status.

## Authority and evidence

The default mode is `copilot`: organize and assess the user's research. Autonomous idea improvement needs an explicit user request or existing manifest/handoff authority. Honor the existing authorization without repeatedly asking.

Use Codex-native shell for ordinary work. `ka_bash_exec` is for formal evidence commands whose command, process and logs must enter the project provenance. Executor tools require explicit authorization and their existing environment/manifest gates; availability does not authorize a run.

`ka_record_main_experiment` records supplied data. Novelty contracts preserve the proposed mechanism and related work without scoring scientific novelty. `ka_claim_gate` checks material completeness, not scientific validity. Verify results and claims against source evidence.

Use `ka_log_digest` and `ka_artifact_index` to locate relevant evidence without loading full logs. If MCP is unavailable, diagnose and repair the connection before mutating research state through another interface.

Report the changed research records, actual verification, remaining uncertainty and next action. Keep detailed logs in project artifacts.
