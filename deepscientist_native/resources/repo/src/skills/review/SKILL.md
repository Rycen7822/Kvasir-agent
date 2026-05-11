---
name: review
description: Run a skeptical evidence-grounded DeepScientist review pass for drafts, paper-like reports, claim scope, and follow-up routing.
version: 1.0.1
author: Orchestra Research
license: MIT
tags: [Review, Paper Review, Revision, Writing, Research]
metadata:
  hermes:
    tags: [Review, Paper Review, Revision, Writing, Research]
    category: user-imported
    related_skills: [research-paper-writing, figure-polish, writing-anti-ai]
    requires_toolsets: [file, terminal, todo, session_search]
skill_role: companion
---

> Codex adapter note: this is a Codex-packaged DeepScientist support skill adapted from the user-local Hermes skill library. Use `scripts/dsctl.py call <ds_tool_name> --json ... --format json` for durable quest state, memory, artifacts, and quest-local shell execution. Load it only when it is the relevant companion to the active stage.
> Core review outputs include `paper/review/review.md`, `paper/review/revision_log.md`, and a concrete claim downgrade / follow-up route when needed.

# Review

Use this skill when the quest already has a substantial draft, paper, or paper-like report and now needs an independent, skeptical, evidence-grounded audit.

This is not the same as ordinary `write`.
It is also not the same as `rebuttal`.

- `write` turns accepted evidence into a narrative.
- `review` audits that narrative like a harsh but constructive expert reviewer.
- `rebuttal` responds to concrete external reviewer pressure that already exists.

## Codex adapter compatibility note

- Treat `quest` as the current task, manuscript workspace, or review target.
- Treat `startup_contract.*` as optional user-provided constraints or manuscript-edit preferences; ignore them when absent.
- Replace legacy shell-wrapper calls with `ds_bash_exec` through `scripts/dsctl.py` for quest-logged shell; ordinary Codex file tools for direct file IO.
- Replace legacy milestone or artifact-interaction hooks with ordinary user-visible progress updates in the assistant response.
- Replace legacy memory helper calls with `session_search(...)`, `ds_memory_write`, and durable local review files as appropriate.
- Route names such as `intake-audit`, `scout`, `analysis-campaign`, `baseline`, `write`, `decision`, `finalize`, and `rebuttal` are workflow labels. If those exact skills are unavailable, use the closest available Codex skills/tools to accomplish the same purpose.

## Interaction discipline

- Follow the shared interaction contract injected by the system prompt.
- For ordinary active work, prefer a concise progress update once work has crossed roughly 6 tool calls with a human-meaningful delta, and do not drift beyond roughly 12 tool calls or about 8 minutes without a user-visible update.
- When the review report, revision plan, or follow-up experiment TODO list becomes durable, send a richer user-visible progress update that says what the main risks are, what should be fixed next, and whether the next route is writing, experiment, or claim downgrade.
- Codex-native execution boundary: use Codex-native file/shell/Git/test/build tools for routine document builds, scripted checks, Git inspection, and file inspection. Use `ds_bash_exec` through `scripts/dsctl.py` only when the command itself must become quest evidence; ordinary Codex file tools are preferred for direct file IO.

## Purpose

`review` is an auxiliary audit skill for paper-like deliverables.

It should convert “the draft feels almost done” into a durable, skeptical, technically grounded review workflow:

1. identify the core claims and likely rejection reasons
2. audit novelty, value, rigor, clarity, and evidence sufficiency
3. write a reliable review note, not vague prose
4. produce a concrete revision plan
5. produce a follow-up experiment TODO list only when the paper truly needs more evidence
6. route the next step cleanly to `write`, `analysis-campaign`, `baseline`, `scout`, or `decision`

Default review stance: independent audit before celebration.
Do not treat “looks polished” as “is defensible”.

## Use when

- a substantial `paper/draft.md`, report draft, or paper-like manuscript already exists
- the quest has enough evidence to support a real audit rather than just speculative comments
- the user asks for:
  - a harsh review
  - a reliable paper audit
  - revision advice before submission
  - a decision about whether more experiments are still needed
- the writing line feels close to done and you need a skeptical gate before stopping

## Do not use when

- the quest still lacks a meaningful draft or report
- the task is ordinary drafting from evidence
- concrete external reviewer comments already exist and the real task is response / revision
  - in that case use `rebuttal`

## Non-negotiable rules

- Review independently. Do not simply mirror previous self-review notes.
- Do not fabricate praise, flaws, citations, novelty overlaps, or fatal defects.
- Keep every serious criticism evidence-grounded.
- Do not recommend more experiments when the real problem is wording, positioning, or claim scope.
- Do not recommend rhetoric when the real problem is missing evidence.
- If novelty or positioning is uncertain, treat that as a literature-audit question first, not an automatic experiment request.
- If a claim is too broad for the evidence, prefer narrowing or downgrading the claim over defending it with style.
- If `startup_contract.review_followup_policy` is present, honor it:
  - `audit_only`
    - stop after durable review artifacts and a clear route recommendation
  - `auto_execute_followups`
    - do not stop at the audit if the next route is already clear; continue into the required experiments and manuscript deltas
  - `user_gated_followups`
    - finish the audit first, then package the next expensive follow-up step into one structured decision
- If `startup_contract.manuscript_edit_mode = latex_required`, treat the provided LaTeX tree or `paper/latex/` as the writing surface when manuscript revision is needed.
- If LaTeX source is unavailable while `latex_required` is requested, do not pretend the manuscript was edited; produce LaTeX-ready replacement text and an explicit blocker note instead.
- Accept manuscript and review inputs from URLs, local file paths, local directories, or current-turn attachments; do not assume the draft is already perfectly normalized.

## Primary inputs

Use, in roughly this order:

- the current paper or report draft
- the selected outline if one exists
- the claim-evidence map if one exists
- the six-field `evaluation_summary` blocks from recent main experiments and analysis slices
- recent main and analysis experiment results
- figures, tables, and captions
- current-turn attachments and user-provided local paths / directories / URLs for the manuscript bundle or review packet
- prior self-review or reviewer-first notes as low-trust auxiliary input
- nearby papers when novelty or comparison is unclear

If the draft/result state is still unclear, perform a quick intake audit first before continuing the review workflow.
Before proposing extra experiments, read those structured `evaluation_summary` blocks first so you do not request work that the recorded evidence already resolved.
If the user provided draft files or manuscript bundles directly, first normalize them into durable working paths before planning experiments or section-level revisions.

## Core outputs

The review pass should usually leave behind:

- `paper/review/review.md`
- `paper/review/revision_log.md`
- `paper/review/experiment_todo.md`
- `paper/paper_experiment_matrix.md` when more evidence is still needed
- `paper/paper_experiment_matrix.json` when more evidence is still needed

Use the templates and references in `references/` when needed:

- `review-report-template.md`
- `revision-log-template.md`
- `experiment-todo-template.md`
- `paper-like-idea-revision.md` for revising a substantial idea/report from external researcher feedback while preserving first-author voice, compact section-level edits, DeepScientist durability, canonical artifact kinds, source fetching/caveats, final mechanical checks, and reviewer-memo pitfalls such as target leakage, baseline category errors, direct-trial controls, and infeasible experiment scale
- `lossless-document-splitting.md` for auditing a long manuscript/report after it has been split into companion documents and the original has been compressed into an index; use it to verify no source sections, tables, formulas, references, or paragraph blocks were lost
- `resource-manifest-tiering.md` for revising a paper-like idea's download list or resource manifest after reading active idea/protocol files; use it to mark main-paper required, Phase-0, implementation, appendix, legacy, reasoning, optional, and reference-only resources without creating a drifting second manifest
- `paper-like-idea-revision.md` also covers repeated DeepScientist split-idea revision hygiene, including `idea/` directory layout: active docs in root, audits in `idea/audits/`, backups in `idea/backup/`, and legacy/source carryover in `idea/archive/`.

## Review dimensions

Audit at least these dimensions:

- research question and value
- novelty and positioning
- method-to-problem fit
- evidence sufficiency
- experimental validity and baseline comparability
- claim scope and over-claiming risk
- writing defensibility and logical flow
- figure / table usefulness
- submission readiness

## Workflow

### 1. Plan the audit

Before writing the review itself, make the audit explicit.

Identify:

- 1 to 3 core claims such as `C1`, `C2`, `C3`
- the strongest current evidence
- the weakest current evidence
- the top 3 likely rejection reasons
- whether the likely next route is:
  - text revision
  - literature / novelty audit
  - baseline recovery
  - supplementary experiment
  - claim downgrade

### 2. Check novelty and positioning only when needed

If novelty, related-work coverage, or field positioning is unclear:

1. open `scout`
2. run a focused literature / comparison audit
3. record what is genuinely overlapping, what remains novel, and what is merely better positioned writing

Do not request new experiments just to answer a literature-positioning question.

### 3. Write a reliable review report

Write `paper/review/review.md` using `references/review-report-template.md`.

The review should be:

- independent
- skeptical but constructive
- technically specific
- reader-aware
- evidence-grounded

At minimum, the review report should cover:

- summary
- strengths
- weaknesses
- key issues
- actionable suggestions
- storyline / outline advice
- priority revision plan
- experiment inventory and research experiment plan
- novelty verification and related-work matrix
- references

If helpful, include an internal conservative overall judgment or score, but do not pretend numerical precision when evidence is still unstable.

### 4. Produce the revision log

Write `paper/review/revision_log.md` using `references/revision-log-template.md`.

For each serious issue, record:

- issue id
- why it matters
- what should change
- whether the fix is writing-only, evidence-only, or experiment-dependent
- whether the issue blocks `finalize`
- one copy-ready replacement sentence / paragraph when feasible
- one LaTeX-ready replacement block when `startup_contract.manuscript_edit_mode = latex_required`

### 5. Produce the follow-up experiment TODO list

Only if more evidence is truly needed, write `paper/review/experiment_todo.md` using `references/experiment-todo-template.md`.

When the paper still lacks experimental support, also create or revise:

- `paper/paper_experiment_matrix.md`
- `paper/paper_experiment_matrix.json`

Treat the matrix as the paper-facing master plan and `paper/review/experiment_todo.md` as only the current execution frontier or review-facing subset.

Each TODO item should include:

- the review issue it answers
- the matrix exp id
- the corresponding `exp_id` in the paper experiment matrix
- why existing evidence is still insufficient
- the minimum experiment or analysis needed
- required metric(s)
- minimal success criterion
- whether this is:
  - analysis of existing results
  - new comparator baseline
  - supplementary experiment
  - figure / table regeneration only

Do not write a vague “run more ablations” list.
Each TODO item should be concrete enough to turn into `analysis-campaign` slices or a `baseline` recovery task.
The matrix should be broader than the TODO list and should classify the full paper-facing experiment space, not just analysis work.
When building or revising that matrix, explicitly consider:

- main comparison packaging or extension
- component ablations
- sensitivity / hyperparameter checks
- robustness checks
- efficiency / cost / latency / token-overhead checks when relevant
- highlight-validation experiments that test the likely strengths of the method
- limitation-boundary analyses
- case study rows as optional rather than mandatory evidence

Do not assume the paper only needs “analysis experiments”.
Do not assume case studies belong in the required set.
If efficiency or cost could become a reviewer-facing strength or concern, put that into the matrix explicitly.

For the matrix, each row should usually record:

- `exp_id`
- `tier`
- `experiment_type`
- `status`
- `feasibility_now`
- `claim_ids`
- `highlight_ids`
- `research_question`
- `hypothesis`
- `comparators`
- `metrics`
- `minimal_success_criterion`
- `paper_placement`
- `promotion_rule`
- `next_action`

The matrix should also keep a short `highlight hypotheses` block.
Do not rely on prose intuition for the method's best selling point; if a likely highlight matters, it should have a corresponding validation row in the matrix.

Before treating the experiments section as stable, require that every currently feasible matrix row that is not merely `optional` or `dropped` is either:

- completed
- analyzed
- excluded with a real reason
- or blocked with a real reason

When extra evidence is truly needed, use the shared supplementary-experiment protocol:

- recover ids / refs first if needed
- write the follow-up work into `paper/review/experiment_todo.md` and mirror it into the current Codex task list when active execution is needed
- represent even one extra run as an explicit named task or analysis slice in local files
- update the experiment matrix and review artifacts after each completed slice

Do not invent a separate review-only experiment workflow.

### 6. Route the next step

After the review artifacts are durable:

- if the issues are mostly narrative or claim-scope fixes, route to `write`
- if novelty / positioning is still unclear, route to `scout`
- if a requested comparator baseline is missing, route to `baseline`
- if new evidence is truly required, route to `analysis-campaign`
- if the route is costly or non-obvious, record a `decision`

Do not stop immediately after writing the review if the next route is already clear.

### 7. Auto follow-up execution contract

When `startup_contract.review_followup_policy = auto_execute_followups`:

- treat the review as a gate, not as the endpoint
- immediately turn the accepted follow-up route into action:
  - `analysis-campaign`
    - when new evidence is truly required
  - `baseline`
    - when a missing comparator baseline blocks fair review
  - `write`
    - when the issues are mostly text, outline, claim-scope, figure, or framing revisions
- after each completed follow-up step, update:
  - `paper/review/revision_log.md`
  - `paper/review/experiment_todo.md`
  - the draft or manuscript-facing revision package
- only treat the review line as truly closed after the follow-up route has either completed or been downgraded / blocked explicitly

When `startup_contract.review_followup_policy = user_gated_followups`:

- stop after the durable audit artifacts
- turn the next expensive follow-up package into one structured decision instead of continuing silently

When `startup_contract.review_followup_policy = audit_only`:

- stop after the durable audit artifacts and route recommendation

## Manuscript revision delivery contract

If manuscript revision is required, make the delta explicit:

- section
- old claim / weakness
- new wording
- evidence basis
- remaining limitation

When the user asks to revise a paper-like idea/report from an external researcher or reviewer memo, treat the memo as edit instructions for the manuscript, not as a discussion prompt:

1. Read the current draft and locate the exact sections that correspond to each critique before editing.
2. Preserve the user's stated voice constraints. If they ask for first-author voice, write as the paper owner; remove advisory phrases such as “should”, “建议”, “可能需要”, and discussion-style hedging unless the manuscript section explicitly needs a limitation.
3. Prefer compact edits to existing paragraphs, tables, formulas, and experiment plans before adding new sections.
4. Patch in small section-level chunks, then reread the changed ranges before continuing.
5. If the memo introduces new papers or baselines, fetch/verify the sources before rewriting claims and record the retrieval surface or caveat.
6. After editing, run a mechanical final pass for forbidden phrases, obsolete claim terms, reference numbering, display-math compatibility, duplicated claims, and overlong paragraphs.

If `startup_contract.manuscript_edit_mode = copy_ready_text`:

- provide copy-ready replacement wording in `paper/review/revision_log.md` or a nearby revision note
- keep the wording directly usable by the user or downstream `write`

If `startup_contract.manuscript_edit_mode = latex_required`:

- prefer editing the actual LaTeX sources when they are available
- otherwise provide LaTeX-ready replacement text blocks with explicit insertion targets
- preserve labels, citations, figure/table refs, and section structure in the suggested replacements

## Companion skill routing

Open additional skills only when the review workflow requires them. These route names are conceptual; if the exact skill is unavailable in Codex, use the closest available skill or direct tool workflow.

- `intake-audit`
  - when the current draft/result/bundle state is still unclear
- `scout`
  - when novelty, positioning, or related-work coverage is genuinely uncertain
- `baseline`
  - when a missing comparator baseline blocks fair review
- `analysis-campaign`
  - when the review identifies concrete evidence gaps that need supplementary runs
- `write`
  - when the review identifies text, outline, claim-scope, or figure revisions
- `figure-polish`
  - when the review identifies figure/table quality as a real weakness
- `decision`
  - when route choice, cost, or claim downgrade is non-trivial

## Artifact routing guidance

Use Codex tools deliberately:

- durable review files under the manuscript workspace
  - review conclusion, claim downgrade recommendation, route choice, stop/go recommendation
- `todo`
  - when the review TODO list should become an explicit follow-up queue
- ordinary assistant progress updates
  - user-visible progress and review milestones
- `ds_bash_exec` for quest-logged shell; ordinary file tools for direct file IO, `read_file`, `search_files`, and `patch`
  - manuscript inspection, edits, verification, and local workflow execution

## Memory discipline

Stage-start requirement:

- run `session_search(...)` when prior work on the same paper, method, or review context may matter
- check current workspace files and, when useful, search prior sessions for:
  - paper title
  - main method name
  - review or self-review
  - key claim or strongest figure

Stage-end requirement:

- if the review produced a durable lesson, claim downgrade, revision rule, or experiment-gap judgment that will matter across sessions, write a concise `ds_memory_write` card or durable local note

Useful tags include:

- `stage:review`
- `type:paper-review`
- `type:revision-plan`
- `type:experiment-gap`
- `type:claim-downgrade`

## Success condition

`review` is successful when:

- a reliable skeptical review note exists
- the highest-risk issues are explicit
- the next revision route is unambiguous
- any needed experiments are captured as a concrete TODO list
- the quest can continue into `write`, `analysis-campaign`, `baseline`, `scout`, or `finalize` without ambiguity

The goal is not to sound severe.
The goal is to make the next revision step technically clear and evidence-bound.
