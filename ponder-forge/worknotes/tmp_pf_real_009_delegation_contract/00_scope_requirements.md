# PF-REAL-009 Scope Requirements

## Status

- planning_document_complete: no
- 100_percent_confidence: no
- current_phase: scratch capture before final repair plan

## Real trigger

Round 1 installed CLI `delegations` for `pf_run_353e985cf14a` produced child contexts that were clear enough for Markdown findings but not enough for parent-submittable JSON reports.

## Hard boundaries

- Modify only `/home/xu/project/autosci-delphi/ponder-forge`.
- Do not modify `/home/xu/project/loop/DeepScientist/quests/001`.
- Keep the fix small; no Hermes core, no idea-spark, no new plugin tool surface.
- Use installed CLI real scenario to verify after source tests and copy install.

## Acceptance requirements

- Child delegation context must include a compact JSON report skeleton with accepted field names.
- Analysis context must expose material `data_result` / `critical` / evidence-group gate expectations.
- Planned role contexts must include one role-duty line, so children do not all receive only generic role names.
- Required evidence text must not be duplicated.
- Tests must prove the generated delegation payload contract.
- Problems and note files must record root cause, fix, and installed real revalidation.
