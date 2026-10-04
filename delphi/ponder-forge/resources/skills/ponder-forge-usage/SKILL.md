---
name: ponder-forge-usage
description: Use FrontierAgent high/max team strategies for complex work with native agents and Ponder CLI state.
---

# Ponder-Forge

Use for a complex research, coding, design, analysis or math problem. The host
owns model execution, delegation, waiting and cancellation. Ponder supplies
FrontierAgent Apodex 1.1 strategy and keeps the task board and complete reports.

## CLI location

Hermes installation: `python3 ${HERMES_HOME:-$HOME/.hermes}/plugins/ponder_forge/cli.py`.
For a source checkout or another host, use the actual absolute `cli.py` path.
The examples below abbreviate this command as `ponder`.

## Workflow

1. `ponder start --goal "..."` defaults to **max**. Choose **high** with
   `--team-effort high`. Profiles are context labels, not fixed team rosters.
2. `ponder plan --run-id R` returns the full coordinator policy. Read it before
   planning; keep it in the coordinator. Use `status` for subsequent short updates.
3. Submit a question-driven board with `plan --run-id R --file board.json`:
   `{"tasks":[{"description":"Question to resolve","owners":[],"resolution":"open"}]}`.
   Update by returned `id`. States: `open`, `in_progress`, `resolved`, `cancelled`.
   `owners` are appended; `replace_owners: true` replaces them. Record cancellation
   reasons in `notes`. A worker report does not automatically resolve its question.
4. Write scoped assignments with `delegations --run-id R --file assignments.json`:
   `{"tasks":[{"agent":"method_a","system_prompt":"Independent literature researcher","prompt":"Specific work","task_ids":["board-id"]}]}`.
   The response contains one complete prompt per assignment. Pass its
   `system_prompt` and `prompt` together to the native agent (these fields do not
   imply a host API system-message override). On Hermes, map prompt to native
   `delegate_task` goal and system_prompt to context; on Codex/Pi, use the native
   agent tools available in that session. Reuse an existing agent for serial follow-ups. Workers return final
   text and do not spawn another team or write Ponder state.
5. After an actual host launch, record it with
   `delegations --run-id R --started TASK_ID --host-agent-id HOST_ID`.
   Merely preparing a payload leaves it queued. Without `--file`, `delegations`
   lists queued work; do not dispatch a task already running on the host.
6. Wait/collect with the native host, then `submit-report --file report.json`:
   `{"run_id":"R","task_id":"TASK_ID","content":"Full returned report"}`.
   Keep all citations, numbers, caveats and negative results. Optional `status`:
   `finished` (default), `partial`, `failed`, `cancelled`; optional confidence 0..1.
   Use `status --run-id R --reports` to read complete recorded reports.
7. Fill gaps, cross-check independent results, and update board resolutions.
   An assignment prompt can use `<attach agent="method_a"/>` to include that
   agent's full latest report from this run. Missing attachments are errors.
   For source arbitration, `verify --run-id R --mode local --file conflict.json`,
   where `{"conflict":"Specific disagreement","report_ids":["report-a","report-b"]}`.
   Execute the prepared local verifier on the native host and retain its reply.
8. Write the **complete** proposed answer to draft.md, then
   `verify --run-id R --mode final --file draft.md`. Execute the prepared final
   verifier. Repair any flaws and re-verify as required by the source policy.
9. `gate --run-id R` checks unresolved board questions. It does not certify
   scientific correctness or demand that every historical assignment finish.
   Save the reviewed answer with `finalize --run-id R --file draft.md`.
   On budget exhaustion/interruption, save `--partial --reason "..."`; unresolved
   questions are retained in the output. Repeating finalize reads the saved result.

## Strategy levels

**high** uses the complete base team workflow: understand and decompose, assign
complementary work, inspect reports and gaps, preserve factual atoms during
synthesis, obtain independent final verification, repair and submit.

**max** adds all five upstream obligations: 2–3 independent axes per nontrivial
sub-question; reinvest into weak, unresolved or disconfirming work; corroborate
load-bearing facts with at least two independent agents and arbitrate conflicts;
run dedicated disproof; final verification re-derives with different queries and
checks every atom before repair and re-verification. Do not weaken these to a
fixed shallow roster. This level does not set the model's reasoning effort.

## Lifecycle and persistence

The batch size defaults to 20 (`start --budget '{"delegate_batch_size":10}'` can
lower it). Actual concurrency and runtime limits belong to the host. `reconcile`
is diagnostic: it does not infer dead processes from age or create retries.
At completion or interruption, stop unneeded native work through the host;
record confirmed cancellations using `delegations --cancelled` before closing the run.

Completed/partial runs are closed to new work. Existing database rows and saved
legacy reports remain readable. Retired lane/child queues are not redispatched;
start a new run for new-strategy work when continuing an old investigation. Outputs include final.md, task_board.json and
reports.json. No claim/evidence JSON schema, content hashes or claim certificates
are required by this workflow.
