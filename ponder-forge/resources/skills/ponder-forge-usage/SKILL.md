---
name: ponder-forge-usage
description: Operate Ponder-Forge complex-problem workflows through the pure CLI.
version: 0.2.0
author: Hermes Agent
---

# Ponder-Forge Usage

Use Ponder-Forge for complex problems that need multiple child agents, structured evidence, independent review, gate checks, and graph-backed finalization.

Ponder-Forge is intentionally operated as a skill + CLI workflow. The installed workflow exposes no Ponder-Forge direct model tools or hooks; use native Hermes `delegate_task` for child execution and the Ponder-Forge CLI for state transitions.

## CLI path

Use the installed plugin CLI path for normal user-facing work:

```bash
PF_CLI="${HERMES_HOME:-$HOME/.hermes}/plugins/ponder_forge/cli.py"
```

For source-tree development only, use the repository-local `cli.py`.

## Core workflow

1. Start a run:

   ```bash
   python3 "$PF_CLI" start --goal "<complex problem>" --profile auto
   ```

2. Plan tasks:

   ```bash
   python3 "$PF_CLI" plan --run-id <run_id>
   ```

3. Produce native delegation payload:

   ```bash
   python3 "$PF_CLI" delegations --run-id <run_id>
   ```

4. Call native Hermes `delegate_task` with the returned `delegate_task_payload`.

5. Collect each child agent's structured JSON report. The parent/controller submits each report through the CLI:

   ```bash
   python3 "$PF_CLI" submit-report --file <report.json>
   ```

   The report JSON must include `run_id`, `role`, `summary`, and profile-appropriate assertions/evidence. Include `task_id` when the report belongs to a planned task. Prefer the exact child report contract embedded in `delegations` output; it contains the active profile's critical assertion type and gate-required evidence groups.

   Child report contract for manual delegations:

   ```json
   {
     "run_id": "<run id>",
     "task_id": "<planned task id>",
     "role": "<planned role>",
     "summary": "short evidence-backed summary",
     "assertions": [
       {
         "assertion_type": "<profile critical assertion type; never leave this placeholder literal>",
         "text": "claim to preserve in final reasoning",
         "importance": 0.9,
         "critical": true,
         "confidence": 0.8,
         "evidence": [
           {
             "evidence_type": "<profile evidence type>",
             "source_ref": "path or command source",
             "quote_or_observation": "observed value or output",
             "command": "exact command if applicable",
             "exit_code": 0
           },
           {"evidence_type": "<another required profile evidence type>", "source_ref": "path", "quote_or_observation": "consistency check"}
         ]
       }
     ],
     "artifacts": [
       {"artifact_type": "report", "path": "path/to/report.md", "summary": "what it contains"}
     ]
   }
   ```

   Children should return this JSON to the parent/controller. Children must not call the CLI themselves; the parent/controller submits reports and records verdicts. Profile anchors: `research` uses `factual_claim`; `coding` uses `code_claim` with `root_cause_trace` plus successful `passing_test` or `execution_log` with `exit_code=0`; `design` uses `design_decision`; `analysis` uses `data_result` with `metric_output.command` and `exit_code=0`; `math` uses `proof_step` plus `critique` or `proof_check` and only positive/unresolved counterexample evidence blocks.

6. Run independent review or record a verdict:

   ```bash
   python3 "$PF_CLI" verify --run-id <run_id> --mode independent_review --target-id <assertion_id>
   python3 "$PF_CLI" verify --run-id <run_id> --mode independent_review --target-id <assertion_id> --reviewer-task-id <task_id> --independent-from-task-id <producer_task_id> --verdict accept --confidence 0.9 --rationale "<why>"
   ```

   The first command creates reviewer tasks and may return a `delegate_task_payload_suggestion`; call native `delegate_task` with that payload, then record each reviewer verdict with the returned reviewer task id and the original producer task id.

7. Check the gate:

   ```bash
   python3 "$PF_CLI" gate --run-id <run_id>
   ```

8. Finalize only when the gate allows it:

   ```bash
   python3 "$PF_CLI" finalize --run-id <run_id>
   ```

9. Inspect status and reconcile only stale running/orphan work:

   ```bash
   python3 "$PF_CLI" status --run-id <run_id>
   python3 "$PF_CLI" reconcile --run-id <run_id>
   ```

   `status.next_required_action="complete"` is terminal. If tasks are still queued or reports are missing, use `delegations --run-id <run_id>` and native `delegate_task`; use `reconcile` for stale running/orphan tasks and follow any returned retry payload.

## Operating rules

- Do not answer finally before `finalize` returns a final report.
- Do not let child agents finalize the run; the parent/controller owns verification and finalization.
- Keep child outputs structured and evidence-backed.
- Use native Hermes `delegate_task` only for child execution; use the Ponder-Forge CLI for Ponder-Forge state transitions.
- Treat CLI JSON with `success=false` as a blocker and fix the cause before continuing.
