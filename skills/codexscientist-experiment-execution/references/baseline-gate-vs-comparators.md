# Baseline gate vs experiment-internal comparators

Session-derived lesson from Quest001 GAAS loop-layer-selection execution.

## Problem

A paper/idea file may use words such as `baseline`, `comparison`, `comparator`, `control`, or method-like names for protocol-internal scores. These should not be automatically promoted into a CodexScientist formal baseline gate object.

In Quest001, the active idea files listed CFC, ETD-score, RR-score, RawRepeat / Original-core Raw repeat-stress, and Middle-cycle. The user corrected that the research should be treated as having no formal CodexScientist baseline. Those names are experiment-internal comparators/controls within the GAAS protocol.

## Correct handling

1. Inspect active `idea/` and protocol files before confirm/waive decisions.
2. Ask: is there a standalone external/reusable baseline artifact to attach/import/reproduce/confirm?
3. If no, waive the baseline gate with a clear reason.
4. In the waiver, preserve internal comparators as experiment conditions so later experiment/write stages still report them.
5. Update command documents that still say `baseline_gate=pending` or suggest `confirm_baseline` for internal comparators.

## Wording pattern

Use language like:

> Baseline gate is waived because this quest has no standalone CodexScientist baseline artifact. CFC / ETD-score / RR-score / RawRepeat / Middle-cycle are experiment-internal comparator scores and controls, not external baseline artifacts. They remain part of the experiment protocol and reporting surface.

## Pitfall

Do not say "no baseline" in a way that erases internal comparisons. The correct meaning is: no formal CodexScientist baseline artifact; internal comparators still exist and must be measured/reported.
