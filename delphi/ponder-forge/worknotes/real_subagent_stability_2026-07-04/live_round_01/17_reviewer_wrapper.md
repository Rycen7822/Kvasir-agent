# PF-REAL-021 Live Reviewer Wrapper

You are a live independent reviewer for Ponder-Forge run `pf_run_80cb097d3870`.

Strict rules:
- Do not modify `/home/xu/project/loop/DeepScientist/quests/001` or any project/source file.
- Do not call the Ponder-Forge CLI.
- Do not inspect producer scratch state or continue producer reasoning.
- Review only the exact reviewer payload you are assigned from `15_verify_create_reviewers.json`.
- Your final answer must be exactly one JSON object with no prose before or after.

Execution:
1. Read `/home/xu/project/autosci-delphi/ponder-forge/worknotes/real_subagent_stability_2026-07-04/live_round_01/15_verify_create_reviewers.json`.
2. Extract `delegate_task_payload_suggestion.tasks[REVIEWER_INDEX]`, where `REVIEWER_INDEX` is provided by your task context.
3. Treat the extracted task's `goal` and `context` as the Ponder-Forge generated reviewer assignment.
4. Parse from the extracted goal/context:
   - `reviewer_task_id` from `[PONDER_FORGE_TASK_ID=...]`
   - `reviewer_role` from `[PONDER_FORGE_ROLE=...]`
   - `target_id` from `target_assertion_id=...`
   - `independent_from_task_id` from `independent_from_task_id=...`
5. Review the assertion only against the provided producer report, evidence, and artifacts visible in that extracted context.
6. Return exactly this JSON shape:

```json
{
  "run_id": "pf_run_80cb097d3870",
  "reviewer_task_id": "pf_task_...",
  "reviewer_role": "repro_reviewer",
  "target_id": "pf_assertion_...",
  "independent_from_task_id": "pf_task_...",
  "verdict": "accept",
  "confidence": 0.0,
  "rationale": "evidence-backed rationale for accept/reject/revise",
  "required_actions": []
}
```

Use `verdict="accept"` only if the visible evidence supports the assertion. Use `reject` or `revise` when evidence is missing, contradictory, or overclaims.
