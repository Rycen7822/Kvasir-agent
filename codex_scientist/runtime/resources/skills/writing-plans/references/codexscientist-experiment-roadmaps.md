# CodexScientist ordered experiment roadmap pattern

Use this reference when a user asks for an experiment execution plan derived from a CodexScientist quest's `idea/` documents.

## Trigger

- User asks for a plan under a root-bound `experiments/` directory.
- User says to read a foundational/index idea document first, then other split idea docs.
- The output should guide later code implementation and experiment execution, not merely summarize the paper idea.

## Recommended output path

`<quest_root>/experiments/EXPERIMENT_EXECUTION_PLAN.md`

## Source reading order pattern

1. `idea/*foundational_report.md` or top-level index/source-map document.
2. `idea/paper_main.md` for claims and main evidence route.
3. `idea/experiment_protocol.md` for candidates, splits, models, metrics, gates.
4. `idea/implementation_spec.md` for code-level score definitions and logging schema.
5. Appendix/theory, related work, reviewer risk register, and download/resource manifest.
6. Quest guide, active requirements, and resource index if present.

## Roadmap sections that worked well

- file purpose and authoritative sources read
- core experimental definitions and protocol boundaries
- current resource/model/data state
- proposed `experiments/` directory layout
- ordered phases from preflight to paper packaging
- baseline/resource gate
- engineering scaffold and testing strategy
- split manifest
- candidate/floorplan enumeration
- trajectory extraction
- chart fitting
- score and baseline implementation
- sanity phase
- main frozen benchmark
- statistics/robustness
- retrofit/recoverability
- appendix experiments
- paper-facing figures/tables/claim validation
- mandatory per-run record format
- CodexScientist artifact/memory rules
- execution discipline
- first next implementation task

## Verification checklist

After writing the roadmap, run a small script/check that verifies:

- expected source docs are mentioned
- all ordered phase IDs are present
- all gates are present
- main models and protocol splits are present
- code fences are balanced
- display math delimiters are balanced
- markdown table row widths are consistent

Then record:

- quest memory with path and summary
- milestone artifact with path, line count/byte count, checks, and next action
