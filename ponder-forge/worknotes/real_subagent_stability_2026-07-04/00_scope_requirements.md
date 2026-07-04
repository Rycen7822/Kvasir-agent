# PF-REAL-021 Scope Requirements

- created_at_beijing: 2026-07-04T22:39:32+0800
- source_dir: `/home/xu/project/autosci-delphi/ponder-forge`
- installed_dir: `/home/xu/.hermes/plugins/ponder_forge`
- real_task_path: `/home/xu/project/loop/DeepScientist/quests/001`
- strict_guard: read-only analysis of quest path; do not modify any code or document under the quest path.
- user goal: make Ponder-Forge repeatedly run real complex tasks, expose issues, fix, reinstall, and continue until all functions including live subagent-executable functions are stable.
- immediate problem: previous clean rounds after PF-REAL-020 validated installed CLI/state/gate/finalize with controller-generated reports, plus one late live lane result. They did not execute three full live lane coordinator rounds with nested child subagents and reviewer subagents.
- classification: PF-REAL-021 proof gap / stability gap.
- required next proof: use installed Ponder-Forge CLI to start/plan/delegations for the real Stage10 task, dispatch actual lane coordinator orchestrator subagents from the generated payload, collect their returned JSON, submit reports, then create/dispatch independent reviewer subagents from verifier payloads, record verdicts, gate/finalize/reconcile/status, and repeat until three clean full-live rounds pass or a plugin problem is found.
- no overclaim rule: until the full live rounds pass, final answer must say all core controller paths are validated but live subagent execution is still in progress or not yet proven.
