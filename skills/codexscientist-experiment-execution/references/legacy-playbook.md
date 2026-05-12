# Legacy playbook

Do not execute old API names directly. This file preserves the pre-upgrade long playbook for audit and migration only. When using it, translate any historical tool or state API names to the current `scripts/csctl.py` command surface and obey the default copilot autonomy gate.

---

---
name: codexscientist-experiment-execution
description: Execute CodexScientist quest experiment command documents with durable cs_* logging, manifest validation, and cautious baseline-gate handling.
version: 1.0.10
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [codexscientist, experiment, manifests, validation, bash-exec]
    category: research
skill_role: companion
---

> Codex adapter note: this support skill is bundled for CodexScientist. Prefer the stable curated MCP tools for repeated CodexScientist state/status/context workflows; use `scripts/csctl.py call <cs_tool_name> --json ... --format json` as CLI fallback. Load at most one support skill alongside the active stage. Runtime state lives under `<project>/CodexScientist/`.

# CodexScientist Experiment Execution

Use this skill when a user asks to execute a CodexScientist quest experiment command document, run preparatory experiment phases, generate resource/split/floorplan manifests, or validate early experiment artifacts.

This is a class-level companion for CodexScientist experiment execution. If the Codex `codexscientist-experiment` skill is available, load it first and treat this skill as local operational guidance for pitfalls and reusable checks discovered in sessions.

## Core rules

- Use Codex/CodexScientist native `cs_*` tools through `scripts/csctl.py` for durable quest state and bash execution; do not call an external legacy CLI.
- Run shell commands through `cs_bash_exec` so session ids, logs, and artifacts remain auditable.
- This skill's support note `references/early-manifest-validation.md` captures the session-derived validation checklist for early resource/split/floorplan manifests.
- This skill's support note `references/baseline-gate-vs-comparators.md` captures the baseline-gate waiver pattern for studies with internal comparators but no formal CodexScientist baseline artifact.
- This skill's support note `references/planned-command-recorders.md` captures the safe execution/validation/reporting pattern for next-step sections whose CLI currently only writes `planned_not_executed` JSON records, including how to stop at a formal runner boundary and optionally add a tiny real forward smoke gate before full runner integration.
- This skill's support note `references/real-runner-backfill.md` captures the TDD pattern for converting a planned-command recorder into the smallest bounded real runner, validating real artifacts, and avoiding overclaiming later-phase results.
- This skill's support note `references/paper-facing-formal-experiment-progression.md` captures the bounded progression pattern for taking over formal experiments whose completion criterion is paper-facing main figures/tables, including source-of-truth precedence, raw-corpus materialization before real forward passes, and documentation/AGENTS synchronization.
- This skill's support note `references/phase2-selector-subset-template.md` captures how to handle Phase 2 selector subset template creation when real Phase 1A results are not yet available.
- This skill's support note `references/phase2-retrofit-plan-blocked.md` captures how to handle the next Phase 2 retrofit-plan step when concrete `MODEL_ID`/`FLOORPLAN_IDS` or real Phase 1A selector outputs are missing.
- This skill's support note `references/phase2-retrofit-preflight-and-corpus-blockers.md` captures how to replace a planned Phase 2 retrofit recorder with a bounded real preflight/blocker runner, how to add an auditable 100M-token streaming corpus provenance gate when materialized text is too small, and how to prevent preflight/corpus substrate progress from being misreported as G2 success.
- This skill's support note `references/phase2-adapter-smoke-to-full-budget.md` captures the next E10 boundary after a real recurrent-core adapter smoke run: validate checkpoint/eval artifacts, keep smoke/partial `Y_recover_smoke` or `Y_recover_partial` separate from formal `Y_recover`, and continue toward a resumable full-budget orchestrator with per-job token-budget gates rather than aggregate-token overclaiming.
- This skill's support note `references/phase2-full-budget-orchestrator-guards.md` captures the E10 `main_100m` resume-chunk guardrails: same-run-dir job-grid/limit reuse checks, append-only chunk records, manifest-backed corpus-consumption as a method gate before formal `Y_recover`, and conservative reporting while G2 is unsatisfied.
- This skill's support note `references/phase2-streaming-cursor-resume.md` captures the persisted streaming-cursor guardrails for cross-invocation corpus progress: load `cursor_before`, select from that cursor, update `cursor_after` only after plan compatibility succeeds, keep append-only consumption history, and keep cursor-validated chunks distinct from formal 100M `Y_recover`.
- This skill's support note `references/phase2-autonomous-resume-loop.md` captures how to run repeated compatible Phase 2 `main_100m` resume chunks in autonomous experiment-only mode: use the quest environment, keep per-chunk JSONL summaries, validate cursor/state/records/checkpoint/eval after every chunk, and avoid overclaiming partial loop progress as formal `Y_recover`.
- This skill's support note `references/formal-experiment-doc-maintenance.md` captures conservative maintenance of long active experiment docs: add compact current-status/navigation pointers, preserve source-of-truth history, verify artifact paths, and keep partial/provenance/corpus-source caveats explicit.
- This skill's support note `references/quest-artifact-memory-pruning.md` captures conservative pruning of quest-local `artifacts/milestones` and `memory/knowledge`: preserve source-of-truth evidence and current handoffs, delete redundant progress/planned/blocked/chunk records, refresh `_index.jsonl`, compact active requirements, and verify counts/status.
- When ongoing experiment documentation becomes too long for reliable continuation, use `codexscientist-quest-handoffs`'s `references/concise-current-status-maintenance.md` pattern: create a short current-status entry, point long command/plan docs to it, preserve source-of-truth history, and verify stale handoff text is gone.

For resumable full-budget Phase 2 runners, verify cross-invocation corpus progress, not just per-invocation sampling. Persist and validate a per-family streaming cursor, keep append-only corpus-consumption history, and ensure incompatible resume attempts fail before cursor/record side effects. For autonomous experiment-only loops that must repeat many compatible chunks, use a quest-local loop summary and the quest's known-good Python environment; do not use bare `python` if the quest has a specific venv/conda environment, and avoid generic background terminal/process execution for CodexScientist work when `cs_bash_exec` can provide durable logs. See `references/phase2-streaming-cursor-resume.md` and `references/phase2-autonomous-resume-loop.md`.
- This skill's support note `references/quest-quickstart-state-repair.md` captures how to repair stale quest quickstart/AGENTS guidance when current quest state diverges from handoff prose.
- Do not claim model results unless real model forward/eval/training artifacts exist. Many early CLI commands may be planning recorders with `planned_not_executed` status.
- Keep baseline gate state explicit. If `baseline_gate=pending` and the user has not chosen confirm/waive, execute only safe preparatory commands and report that the gate is still pending.
- Distinguish formal CodexScientist baselines from experiment-internal comparators. Named scores/controls in idea files (for example CFC, ETD-score, RR-score, RawRepeat, Middle-cycle in GAAS-style protocols) are not automatically baseline artifacts; if the active idea/protocol says the study has no standalone baseline, waive the gate and preserve those names as internal comparators/ablation conditions.

## Baseline gate and comparator handling

When a command document mentions a baseline gate, inspect active `idea/` and protocol files before deciding whether to confirm or waive. Do not infer a formal baseline solely from words like `baseline`, `comparison`, `comparator`, or `control` in the paper plan.

Use this distinction:

- Formal CodexScientist baseline: a standalone external/reusable reference object to attach, import, reproduce, verify, and record under the quest's baseline roots.
- Experiment-internal comparator: a score, heuristic, ablation, direct-trial control, conditional analysis, or stress test computed inside the current protocol.

If the user or idea files indicate there is no formal baseline, call the waiver route and record why. In the waiver/milestone, explicitly state that internal comparators remain part of the experiment and writing surface; the waiver only clears the CodexScientist gate. Afterward, patch any command document sections that still say `baseline_gate=pending` so future execution does not keep re-asking for baseline confirmation.

## Step-number ambiguity

When a user says "execute 0~3 steps" from a command document, inspect the document before acting. Two numbering systems may coexist:

- document headings such as `0`, `1`, `2`, `3`
- experiment identifiers such as `E00`, `E01`, `E02`, `E03`

If the ambiguity can safely be resolved by executing a broader bounded preparatory scope, include both interpretations (for example heading 0-3 plus E00-E03) and explicitly state what was included. Do not silently stop after only the heading interpretation if later non-training manifest steps are likely prerequisites for the next phase.

## Early-stage execution pattern

1. Record the user requirement in quest state if CodexScientist mode is active.
2. Read the command document section to be executed; do not rely on memory.
3. Execute setup/environment/resource/smoke commands with one stable `RUNSTAMP` so outputs are correlated.
4. For preparatory commands, generate:
   - resource manifest
   - environment snapshot
   - test/smoke logs
   - dataset split manifest
   - floorplan manifest and summary when requested
5. Validate each artifact from disk, not only from stdout.
6. Write a compact run summary JSON/MD under a quest-local logs/manifests directory.
7. Record a milestone only after validation passes, or record a blocked/partial milestone if validation fails.

## Schema-aware manifest validation

Validate generated manifests against the actual file schema. Do not reject a valid artifact only because the generated summary uses different wording than the prose command document.

For current `planned_not_executed` CLI recorders, stdout logs may be zero bytes because the command only writes the JSON command record and emits no terminal output. Treat an empty stdout log as acceptable if the JSON artifact exists, parses, has the expected command/schema/status, and the command exit code was zero. Do not rerun or mark the step failed solely because the tee-created stdout log is empty.

Recommended checks:

- resource preflight: model config/tokenizer/weights booleans are true; resource manifest exists and has a SHA256.
- split manifest: record count is nonzero; `no_overlap_verified` is true; each record has dataset family/name, split name, document/shard id, domain group, answer-span exclusion flag, streaming route, and local metadata path.
- floorplan manifest: JSONL parses; records are nonzero; each record has traceability fields such as `model_id`, `L`, `p`, `q`, `r`, `T_F`, `c`, `executed_depth`, `candidate_set`, `validity_flags`, `floorplan_id`, and `mode`; `F_main` records have integer `c > 0` and include `C_nonempty` in `validity_flags`.

If a generated summary omits fields that are present in the manifest, append a small traceability audit or create a sidecar summary instead of treating the run as failed. See `references/early-manifest-validation.md`.

## Planned-command recorder steps

When continuing an experiment sequence and the next section invokes a command that currently returns `status: planned_not_executed`:

- infer the next bounded step from the command document and the latest run summary, then stop after that step;
- validate the JSON command record from disk rather than relying on stdout;
- allow a zero-byte stdout log only when the command is a planned recorder and the JSON record validates;
- explicitly report that no real model forward/eval/training or scientific artifacts were produced;
- for multi-part steps (for example E04 Phase 0+Phase 1A trajectories or E06 Phase 0+Phase 1A scoring), validate every command record before declaring the step complete;
- preserve comparator semantics: CFC, ETD-score, RR-score, RawRepeat, Middle-cycle, GAAS, and GAAS+Coda are experiment-internal scores unless a formal external baseline artifact is explicitly introduced;
- write a run summary and milestone with the exact `stopped_after` step.

For Phase 2 selector subset setup after Phase 1B, treat template creation as its own bounded step when real Phase 1A results are unavailable: create `phase2_selector_subset.template.json`, do not create or use `phase2_selector_subset.json`, do not run retrofit planning/training, and report `completed_template_only`. See `references/phase2-selector-subset-template.md`.

For the next Phase 2 retrofit-plan step (for example E10.2), do not run `gaas_loop.cli retrofit` with placeholder or guessed values. If real Phase 1A results, `phase2_selector_subset.json`, `MODEL_ID`, or `FLOORPLAN_IDS` are missing, perform a prerequisite check, write a blocked summary, report `blocked_missing_phase1a_selection`, and stop before later steps. See `references/phase2-retrofit-plan-blocked.md`.

After real selector inputs exist, the next missing formal boundary may still be a planned `run-phase2-retrofit` recorder. In that case, convert the command to a bounded real preflight/blocker runner before claiming Phase 2 evidence: validate selector inputs and corpus budget from disk, write resolved config/metrics/blocker/claim-validation manifests, set `planned_not_executed=false` only for the preflight itself, and keep `training_executed=false`, `writes_y_recover=false`, and `g2_satisfied=false` when corpus size or the training loop is still missing. If materialized local text is far below the configured budget but official dataset metadata/shards are available, add a separate corpus provenance gate that fixes the token-budget mix before outcomes, writes an active streaming-corpus manifest, validates sample shards and token quota, then rerun preflight so the remaining blocker becomes the missing training/eval loop—not G2 completion. See `references/phase2-retrofit-preflight-and-corpus-blockers.md`.

Once the training/eval loop is implemented, run a bounded adapter-smoke before attempting paper-scale training. Validate real checkpoint and interval-eval artifacts, but classify the smoke as substrate validation only when its tokenizer-counted tokens are below the protocol budget. Keep `writes_y_recover=false`, report only smoke-level recovery records such as `Y_recover_smoke`, and continue under E10 toward a resumable full-budget orchestrator with checkpoint resume, fixed selector/rank/seed grid, interval eval, and candidate-level `Y_recover` after the 100M-token budget is actually reached. See `references/phase2-adapter-smoke-to-full-budget.md`.

When the user explicitly authorizes taking over formal experiments and backfilling steps that were previously only planned, convert the earliest missing recorder into a bounded real runner before claiming later stages. Use TDD with a deterministic fixture backend first, then run the real bounded command via `cs_bash_exec`, validate artifacts from disk, and record a main experiment plus milestone/decision. If a real bounded run uses synthetic/provenance prompts because raw corpus text is absent, say so; do not present it as full paper-scale corpus extraction. See `references/real-runner-backfill.md`.

When the user's completion criterion is paper-facing completeness (for example "all main figures completed and all main tables filled with formal experiment data"), keep progressing one bounded formal experiment at a time rather than jumping to paper packaging. Treat active `idea/` documents as the highest-precedence source when they conflict with command docs, AGENTS, implementation, or handoff prose; update the formal command document and AGENTS after each verified step. If the next real runner requires score-side or target-side data, keep these boundaries explicit (for example candidate scoring must not write `Y_frozen`/`Y_recover`). See `references/paper-facing-formal-experiment-progression.md`.

See `references/planned-command-recorders.md` for the detailed Quest001-derived checklist.

## Quest quickstart / AGENTS state repair

During experiment execution, quest-local quickstart files such as `AGENTS.md` can lag behind durable quest state and formal command documents. If a stale quickstart says `baseline_gate=pending`, "confirm/attach baseline first", or similar while `cs_get_quest_state` and the command document show `baseline_gate=waived`, repair the quickstart before or alongside the next experiment step.

Use this pattern:

1. Treat `cs_get_quest_state` plus the active command document as source of truth over handoff prose.
2. Patch quickstart text to state the current gate state, decision artifact path when known, and comparator semantics.
3. If both a source quest copy and a loop/workspace copy of `AGENTS.md` exist, repair both and verify they are identical after patching.
4. Search the file(s) for stale phrases such as `baseline_gate.*pending`, `Confirm/attach`, `still pending`, `no baseline is confirmed yet`, and stale active-stage text that conflicts with durable quest state.
5. Include the quickstart repair in the run summary and milestone when it is part of the user's requested continuation.

See `references/quest-quickstart-state-repair.md` for the Quest001-derived checklist.

## Git and checkpoint hygiene

After artifact recording/checkpointing, inspect quest-local status for unintended deletions or overwritten manifests. If a checkpoint reports deleted generated artifacts, verify whether that is expected before moving on. Repair or explain unexpected tracked-file changes in the next milestone.

If `cs_record_main_experiment` returns an optional Pillow / metric timeline chart error after a call with numeric `metrics_summary`, verify `experiments/main/<run_id>/RUN.md`, `RESULT.json`, and `artifacts/runs/*.json` before retrying: the record may already have been written and committed before chart generation failed. Use a milestone/decision to finish durable routing if the main run files are present.

When calling `cs_record_main_experiment`, pass narrative fields such as `notes` in the shape the tool expects (prefer a list of note strings if available). Passing a plain string to a list-like field can render as one character per bullet in `RUN.md` / `RESULT.json`; if this happens, patch the generated main run files immediately before recording the milestone/decision. For `cs_artifact_record(kind="decision")`, put the decision payload in the `payload` object with `kind`, `verdict`, `action`, and `reason`; keep `payload.action` to the recorder's known route enum such as `continue` instead of a full sentence, and put the prose route in `next_action`, `reason`, or `summary`. Some top-level decision fields are ignored by the generic recorder, and unknown action strings can fail validation.

## Active-doc maintenance during formal experiments

When experiment docs have become too long or stale, do not clean by pruning evidence. Add/update compact navigation surfaces, point long docs to current status, verify artifact paths, and keep method caveats explicit. In particular, document manifest-backed bounded corpus consumption separately from true streamed-shard corpus training, and answer plan-completion questions directly: active E-step, formal `Y_recover` status, G2 status, later-step entry status, and whether the GAAS Loop Layer Selection plan is fully complete. See `references/formal-experiment-doc-maintenance.md`.

## Reporting

A completion reply should include:

- completion time
- runstamp
- exact executed scope
- pass/fail status
- key validation results
- important output paths
- baseline-gate status
- whether real model forward/eval/training was or was not started
