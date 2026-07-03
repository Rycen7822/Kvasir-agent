---
name: ponder-forge-usage
description: Operate Ponder-Forge complex-problem workflows through the pure CLI.
version: 0.2.0
author: Hermes Agent
---

# Ponder-Forge Usage

Use Ponder-Forge for complex problems that need multiple child agents, structured evidence, independent review, gate checks, and graph-backed finalization.

Ponder-Forge is intentionally operated as a skill + CLI workflow. It does not expose Ponder-Forge direct model tools by default.

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

   The report JSON must include `run_id`, `role`, `summary`, and profile-appropriate assertions/evidence. Include `task_id` when the report belongs to a planned task.

   Child report contract for manual delegations:

   ```json
   {
     "run_id": "<run id>",
     "task_id": "<planned task id>",
     "role": "<planned role>",
     "summary": "short evidence-backed summary",
     "assertions": [
       {
         "assertion_type": "<profile assertion type such as data_result>",
         "text": "claim to preserve in final reasoning",
         "importance": 0.9,
         "critical": true,
         "confidence": 0.8,
         "evidence": [
           {
             "evidence_type": "metric_output",
             "source_ref": "path or command source",
             "quote_or_observation": "observed value or output",
             "command": "exact command if applicable",
             "exit_code": 0
           },
           {
             "evidence_type": "sanity_check",
             "source_ref": "path",
             "quote_or_observation": "consistency check"
           }
         ]
       }
     ],
     "artifacts": [
       {"artifact_type": "report", "path": "path/to/report.md", "summary": "what it contains"}
     ]
   }
   ```

   Children should return this JSON to the parent/controller. Children must not call the CLI themselves; the parent/controller submits reports and records verdicts.

6. Run independent review or record a verdict:

   ```bash
   python3 "$PF_CLI" verify --run-id <run_id> --mode independent_review --target-id <assertion_id>
   python3 "$PF_CLI" verify --run-id <run_id> --mode independent_review --target-id <assertion_id> --reviewer-task-id <task_id> --independent-from-task-id <producer_task_id> --verdict accept --confidence 0.9 --rationale "<why>"
   ```

7. Check the gate:

   ```bash
   python3 "$PF_CLI" gate --run-id <run_id>
   ```

8. Finalize only when the gate allows it:

   ```bash
   python3 "$PF_CLI" finalize --run-id <run_id>
   ```

9. If tasks are stale or missing reports, inspect status and reconcile:

   ```bash
   python3 "$PF_CLI" status --run-id <run_id>
   python3 "$PF_CLI" reconcile --run-id <run_id>
   ```

## Operating rules

- Do not answer finally before `finalize` returns a final report.
- Do not let child agents finalize the run; the parent/controller owns verification and finalization.
- Keep child outputs structured and evidence-backed.
- Use native Hermes `delegate_task` only for child execution; use the Ponder-Forge CLI for Ponder-Forge state transitions.
- Treat CLI JSON with `success=false` as a blocker and fix the cause before continuing.
