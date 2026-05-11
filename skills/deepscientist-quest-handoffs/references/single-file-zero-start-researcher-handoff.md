# Single-file zero-start researcher handoff

Use when the user wants to give another researcher one Markdown file that is sufficient to start analysis from scratch, without relying on chat history, code, or a broad zip.

## When to choose this

- The user says the package or docs are still too cluttered.
- The recipient is an external researcher who needs to understand and critique the project, not rerun it.
- The user asks for "all necessary information in one md file", "from zero", "quick start", or "handoff for analysis".

## Output shape

Write one quest-root Markdown file, e.g.:

- `RESEARCHER_ZERO_START_ANALYSIS.md`

Keep it self-contained enough that the reader can understand the project without opening chat history. If the recipient will also receive the quest tree or a zip, the file may cite relative paths for verification while summarizing the necessary facts inline. If the user says the other researcher will not receive other files, do **not** make evidence paths a primary section; instead embed the idea, protocol, experiment facts, numeric results, caveats, and reviewer questions directly in the Markdown. File paths can be omitted entirely except for the local output path reported back to the user.

Recommended sections for a true one-file recipient:

1. handoff timestamp, intended reader, and scope guard;
2. one-paragraph project positioning;
3. research question and what the project is not claiming;
4. key terminology and method components;
5. protocol / information-boundary summary;
6. self-contained idea and method summary, including GAAS components and candidate-set definitions;
7. exact-enough key function definitions: formulas, normalization, thresholds, aggregation, tie/percentile convention when known, and explicit "unknown/not yet audited" markers for anything not recovered;
8. self-contained experiment implementation summary: how candidates are enumerated, how calibration/eval batches are used, how adapters/checkpoints/logs/metrics are produced, what is frozen/trainable, optimizer/schedule/budget/eval cadence if known, and what is not implemented/run;
9. self-contained experiment design, including models, data splits, phases, and success criteria;
10. key result tables or compact result bullets with numbers inline;
11. traceability / verification interpretation without relying on external paths;
12. safe claims vs unsafe claims;
13. known limitations and suggested reviewer questions;
14. suggested analysis workflow for the new researcher;
15. operational boundaries: no rerun, no code/package assumptions, no secondary workspace sync unless requested.

## Workflow

1. Record the user requirement in quest state when DeepScientist mode is active.
2. Read the current status, main result report, active idea/protocol/spec docs, and final evidence artifacts. If the file must let a researcher judge implementation correctness, also read the active code/config/resolved run records that define how scores, candidates, adapters, batching, optimizer, checkpoints, eval rows, and verification fields are actually produced; do not infer these details from prose specs alone. If the user says "边读边写" or similar, explicitly loop back after the first draft to read any missed source-of-truth files and patch the handoff.
3. Write the single Markdown file under the quest root.
4. Validate both structure and references:
   - file exists and is nonempty;
   - line/byte count is reasonable;
   - required section headings or phrases are present;
   - referenced key paths exist;
   - conservative claim boundaries are explicit.
5. Record a milestone with the handoff path, source files checked, claim boundaries, line count, and validation result.

## Pitfalls

- Do not make the single file a long pasted transcript or command diary. It should be a curated analysis entry, not another history log.
- Do not only provide a short description if the user asked for all necessary information in one file.
- Do not assume a zip recipient will inspect every file; put the central facts and caveats in the Markdown itself.
- Do not collapse raw runner verification and post-hoc traceability into one success statement. Preserve source fields and explain their relationship.
- Do not present normative method formulas as if they are the active runner implementation. When specs and code/config diverge, write both: "normative intent" and "active implementation", including any score proxy, aggregation, schedule, batching, or eval-cadence mismatches that affect scientific judgment.
- Do not include code, commands to rerun, or model/checkpoint material unless the user explicitly asks for a reproduction package.
- If a previous broad package confused the user, prefer a minimal single-file handoff before expanding artifacts again.
