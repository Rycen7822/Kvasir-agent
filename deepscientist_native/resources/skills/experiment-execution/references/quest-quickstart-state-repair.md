# Quest quickstart state repair notes

Use when a DeepScientist quest-local quickstart file (for example `AGENTS.md`) contains stale state that conflicts with `ds_get_quest_state`, formal experiment command documents, or recently recorded decisions.

Quest001-derived pattern:

- Stale quickstart text said `Baseline gate: pending`, "Confirm/attach the baseline first", and "baseline_gate is still pending".
- Current durable state and formal command document had `baseline_gate=waived` after decision `artifacts/decisions/decision-9e452653.json`.
- CFC / ETD-score / RR-score / RawRepeat / Middle-cycle were clarified as experiment-internal comparators/controls, not formal DeepScientist baseline artifacts.

Repair checklist:

1. Read the relevant quickstart sections and search for stale phrases:
   - `baseline_gate.*pending`
   - `Baseline gate: `pending``
   - `Confirm/attach`
   - `still pending`
   - `no baseline is confirmed yet`
2. Patch the file to say the current durable state, not the old handoff state.
3. If a waiver/decision artifact exists, include its relative path.
4. State comparator semantics explicitly when old text might cause re-confirming a non-baseline comparator.
5. Re-run the stale-phrase search after patching.
6. If the user asked to continue an experiment and repair the file in the same turn, include both the quickstart repair and the experiment step in the run summary and milestone.

Reporting wording:

- "AGENTS.md repaired: old baseline_gate=pending guidance removed; file now follows current quest state baseline_gate=waived."
- Do not imply the research has no comparators; say the named scores remain experiment-internal comparators/controls.
