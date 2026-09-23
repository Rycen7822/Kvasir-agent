---
name: kvasir-agent-write
description: Draft and revise research papers from recorded evidence, connect claims to analysis, and prepare review responses and final paper bundles.
---

# Research writing and review

1. Read `ka_research_read(operation="resume")`, relevant analysis records and source evidence. Identify the contribution, measured results, limitations and intended venue. Use native Codex planning for the writing task.
2. Prepare or revise an outline with `ka_paper_record(operation="outline")`. Map each proposed claim to baseline, metric, experiment and completed analysis slices. Use `ka_claim_gate` to find missing material; review scientific validity separately.
3. Use strict literature research and paper reliability workflows where sources need qualification. Cite the actual paper and distinguish accepted venue evidence from preprint status or citation popularity.
4. Draft with Codex-native file tools. Keep measurements and uncertainty faithful to the recorded results; never invent missing experiments, reviewer feedback or citations.
5. For review or rebuttal, make a compact issue-to-evidence list. State which response needs new analysis or a new experiment and honor the user's authorization before execution. Use `ka_research_read(operation="review")` to locate current review artifacts.
6. Render and inspect figures and the final document. Use figure-polish only for figure work. Check references, claim wording, tables and unresolved limitations.
7. Record the paper manifest with `ka_paper_record(operation="bundle")`, update the research summary with native file editing where useful, and checkpoint reviewed artifacts and open issues. Bundle creation does not publish or submit the paper.

## Supporting material

Consult only the relevant historical section; current tool schemas define callable APIs:

- [Writing](references/legacy-playbook.md)
- [Review](../../docs/research-playbooks/kvasir-agent-review/references/legacy-playbook.md)
- [Rebuttal](../../docs/research-playbooks/kvasir-agent-rebuttal/references/legacy-playbook.md)
- [Finalization](../../docs/research-playbooks/kvasir-agent-finalize/references/legacy-playbook.md)
