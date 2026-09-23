---
name: kvasir-agent-experiment
description: Establish research baselines, record testable ideas and experiments, and connect measured outcomes to analysis and negative-result memory.
---

# Evidence-backed experiments

Use for the research lifecycle from baseline to analysis. Use Codex-native tools for code, tests and routine commands; preserve research meaning with MCP.

1. Recover constraints with `ka_research_read(operation="resume")`. Identify the baseline, metric definition and direction, evaluation data, protected evaluator files, resource limits and existing run evidence.
2. Register and validate an environment when execution needs protected-file hashes, dataset identity, or trajectory lineage. Otherwise use `ka_baseline(operation="create")` and `ka_baseline(operation="confirm")` for the local baseline contract. A stub or waiver is not a measured baseline; record that limitation.
3. Record an idea with `ka_method_record(operation="idea")`: mechanism, specific related-work references and expected difference are required. Check recorded negative results before repeating a failed mechanism. The contract is an unverified research hypothesis; the plugin supplies no novelty score.
4. Form a small experiment plan with its hypothesis, comparison, metric, seeds, expected evidence and stopping condition. Respect existing authorization. Use `ka_bash_exec` only for formal provenance; executor scheduling additionally requires the explicit executor gates.
5. Inspect actual logs and metric files. Use `ka_feedback_ingest` for environment-linked feedback and trajectories. Record outcomes and evidence paths with `ka_record_main_experiment`; `recorded_only` does not establish execution success or validity.
6. Record failures with `ka_method_record(operation="negative")` and measured changes with `ka_method_record(operation="result")`. Do not convert missing measurements into improvement claims.
7. Create an analysis campaign with writing targets and required slices, record each slice, and run `ka_claim_gate` before using a conclusion in a paper. A complete material set still needs scientific review, appropriate controls and uncertainty analysis.
8. Checkpoint the decision, evidence and next step.

## Supporting material

Read a relevant section only when needed. These historical playbooks preserve domain detail; use current MCP schemas for APIs:

- [Experiment details](references/legacy-playbook.md)
- [Baseline considerations](../../docs/research-playbooks/kvasir-agent-baseline/references/legacy-playbook.md)
- [Analysis considerations](../../docs/research-playbooks/kvasir-agent-analysis-campaign/references/legacy-playbook.md)
- [Execution evidence](../../docs/research-playbooks/kvasir-agent-experiment-execution/references/legacy-playbook.md)
