# CodexScientist code-only implementation passes

Use this reference when the user asks to implement experiment code from a CodexScientist experiment roadmap while explicitly forbidding real experiments.

Session-tested pattern (Quest 001 GAAS loop-layer selection, 2026-05-03):

1. Treat source priority as part of the plan, not only chat context. Record it near the top of the implementation plan, e.g. `idea/` active docs > `EXPERIMENT_EXECUTION_PLAN.md` > `代码实现plan.md`.
2. Create the requested implementation plan before writing code. For this user, a Chinese `experiments/代码实现plan.md` with sections like `使用规则（禁止改动）`, `当前硬约束`, `当前事实快照`, `当前主线执行顺序`, `当前阶段任务`, and `当前阶段进展` worked well.
3. Include an explicit prohibition line: code/config/tests/static checks only; no real experiment, no model forward pass, no trajectory extraction, no frozen evaluation, no retrofit training.
4. Define allowed checks: `py_compile`, CLI `--help`, unit tests, static lint, and fixture/dry-run smoke tests that write `planned_not_executed` manifests.
5. After every implementation step, re-open/read the plan and update the checkbox immediately with a short completion note: timestamp, files, and function. Do not wait until the end to reconcile all checkboxes.
6. Keep experiment-like CLI entries safe by default. Commands such as `run-phase0`, `run-phase1a-frozen`, and `run-phase2-retrofit` should emit `planned_not_executed` manifests unless the user later authorizes real execution.
7. Validation bundle for a code-only pass should include: source/test `py_compile`, CLI help, pytest, lint, and smoke generation of manifests in the experiment workspace or a temp dir. State explicitly that these are not real experimental results.
8. Record durable state at the end: quest memory for reusable implementation status and a milestone artifact with paths, validation summary, and the no-experiment scope.

Pitfalls:

- If a bulk file-writing script fails before execution, record the failure in the implementation plan and switch to smaller patches.
- CodexScientist memory writes may require a `title`; if a title-less write fails, retry with a compact title and mention the recovery in the artifact note.
- Do not call code-level manifest generation an experiment result. It is preflight/dry-run evidence only.
