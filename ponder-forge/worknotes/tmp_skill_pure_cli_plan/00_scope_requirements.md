# Scope Requirements — Ponder-Forge skill + pure CLI

- captured_at: 2026-07-04T06:11:31+08:00
- source_dir: `/home/xu/project/autosci-delphi/ponder-forge`
- installed_dir: `/home/xu/.hermes/plugins/ponder_forge`
- final_plan_path: `/home/xu/project/autosci-delphi/ponder-forge/worknotes/2026-07-04-skill-pure-cli-implementation-plan.md`
- design_artifact_path: `/home/xu/project/autosci-delphi/ponder-forge/worknotes/tmp_skill_pure_cli_plan/design_audit.md`

## User request

Convert Ponder-Forge into a true `skill + pure CLI` workflow, then implement the plan. The installed plugin should no longer add many model-visible tools that consume context. The implementation must follow the writing-plans workflow, use small patches, keep `note.md` current, avoid over-design, remove dead code/files, and perform confidence-repair loops after each slice.

## Required outcome

1. Ponder-Forge core remains usable from the installed plugin directory.
2. The default Hermes plugin registration exposes no model-visible Ponder-Forge tools and no Ponder-Forge hooks.
3. The user-facing workflow is driven by a bundled skill plus a pure Python CLI.
4. The CLI must cover the existing public workflow: start, plan, delegations, submit report, verify, gate, status/pool, finalize, reconcile.
5. The bundled skill must instruct agents to use the CLI via terminal, not direct Ponder-Forge tools.
6. Tests must prove the old workflow is available through CLI and that plugin registration no longer exposes the 9 tools / 6 hooks.
7. Installed-copy verification must pass after copy install.

## Constraints

- Do not modify `/home/xu/project/loop/DeepScientist/quests/001`.
- Touch only Ponder-Forge files unless a test command reads repository state.
- Do not introduce a packaging framework or dependency if a stdlib CLI is sufficient.
- Do not keep dead tool/hook code visible as a public contract unless tests prove it is intentionally internal-only.
- Do not overfit to this current TUI handler surface; final verification must use source tests and installed copy tests.

## Non-goals

- No new daemon, MCP server, web UI, queue runner, or background service.
- No automatic child-agent orchestration beyond producing native `delegate_task` JSON payloads.
- No migration of existing `~/.hermes/ponder_forge` SQLite schema; existing state stays compatible.
- No attempt to remove Hermes native `delegate_task`; the skill continues to use it after the CLI emits payload JSON.

## Current status

- Planning: in progress, not complete.
- Implementation: not started.
- Confidence: not yet 100%; design artifact and final plan still need review.
