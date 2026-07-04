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

1. Start a run. Omit `--budget-json` for the default 8x4 swarm, or pass positive integer budget keys explicitly:

   ```bash
   python3 "$PF_CLI" start --goal "<complex problem>" --profile auto --budget-json '{"top_level_runs": 8, "child_concurrency_per_lane": 4}'
   ```

2. Plan tasks:

   ```bash
   python3 "$PF_CLI" plan --run-id <run_id>
   ```

   `plan` creates queued lane coordinator tasks plus planned lane-child backlog rows. `top_level_runs` controls the number of top-level lane coordinators. `child_concurrency_per_lane` is the maximum number of child subagents a lane coordinator may have in flight at once; it does not cap the total planned child backlog.

3. Produce native delegation payloads for lane coordinators:

   ```bash
   python3 "$PF_CLI" delegations --run-id <run_id>
   ```

4. The parent/controller calls native Hermes `delegate_task` with the returned `delegate_task_payload`. Lane coordinator payloads use native `role="orchestrator"`.

5. Each lane coordinator calls native `delegate_task` for only the child tasks in its manifest. Run repeated child waves with at most `child_concurrency_per_lane` child subagents in flight at once. The lane coordinator then returns one lane report JSON with `child_reports`.

6. The parent/controller submits each lane report through the CLI:

   ```bash
   python3 "$PF_CLI" submit-report --file <report.json>
   ```

   The lane report JSON must include `run_id`, the lane coordinator `task_id`, `role`, `summary`, `child_reports`, `assertions`, and `artifacts`. Prefer the exact lane report contract embedded in `delegations` output; it contains the active profile's critical assertion type and gate-required evidence groups.

   Lane report contract for manual delegations:

   ```json
   {
     "run_id": "<run id>",
     "task_id": "<lane coordinator task id>",
     "role": "swarm_lane_coordinator",
     "summary": "lane-level synthesis",
     "child_reports": [
       {
         "task_id": "<planned child task id>",
         "role": "<planned child role>",
         "summary": "short evidence-backed child summary",
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
     ],
     "assertions": [],
     "artifacts": []
   }
   ```

   Children return child JSON to their lane coordinator. Lane coordinators return one lane report to the parent/controller. Neither child agents nor lane coordinators call the Ponder-Forge CLI; the parent/controller submits reports and records verdicts. Profile anchors: `research` uses `factual_claim`; `coding` uses `code_claim` with `root_cause_trace` plus successful `passing_test` or `execution_log` with `exit_code=0`; `design` uses `design_decision`; `analysis` uses `data_result` with `metric_output.command` and `exit_code=0`; `math` uses `proof_step` plus `critique` or `proof_check` and only positive/unresolved counterexample evidence blocks.

7. Inspect status until the swarm topology is complete:

   ```bash
   python3 "$PF_CLI" status --run-id <run_id>
   ```

   `status.swarm` reports lane count, child backlog count, finished lane/child counts, queued delegation count, and incomplete task count. If `next_required_action` is `delegations`, call `delegations` and native `delegate_task`; if it is `submit-report`, submit missing lane reports.

8. Run independent review or record a verdict after lane and child reports are submitted:

   ```bash
   python3 "$PF_CLI" verify --run-id <run_id> --mode independent_review --target-id <assertion_id>
   python3 "$PF_CLI" verify --run-id <run_id> --mode independent_review --target-id <assertion_id> --reviewer-task-id <task_id> --independent-from-task-id <producer_task_id> --verdict accept --confidence 0.9 --rationale "<why>"
   ```

   The first command creates reviewer tasks and may return a `delegate_task_payload_suggestion`; call native `delegate_task` with that payload, then record each reviewer verdict with the returned reviewer task id and the original producer task id.

9. Check the gate:

   ```bash
   python3 "$PF_CLI" gate --run-id <run_id>
   ```

10. Finalize only when the gate allows it:

   ```bash
   python3 "$PF_CLI" finalize --run-id <run_id>
   ```

11. Reconcile only stale running/orphan work:

   ```bash
   python3 "$PF_CLI" reconcile --run-id <run_id>
   ```

   `status.next_required_action="complete"` is terminal. If tasks are still queued or reports are missing, use `delegations --run-id <run_id>` and native `delegate_task`; use `reconcile` for stale running/orphan tasks and follow any returned retry payload.

## Operating rules

- Do not answer finally before `finalize` returns a final report.
- Do not let child agents finalize the run; the parent/controller owns verification and finalization.
- Keep child outputs structured and evidence-backed.
- Use native Hermes `delegate_task` only for child execution; use the Ponder-Forge CLI for Ponder-Forge state transitions.
- Treat CLI JSON with `success=false` as a blocker and fix the cause before continuing.
