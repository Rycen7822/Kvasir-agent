# Real-runner backfill from planned-command recorders

Session-derived pattern from Quest001 E04.1 (GAAS trajectory extraction), for cases where a formal experiment command exists but the CLI subcommand still returns `planned_not_executed`.

## When to use

Use when the user asks to take over formal experiments or backfill earlier formal steps, and the command document shows a planned recorder for a step that should produce scientific artifacts.

## Workflow

1. Re-read the formal command document and the latest run state; choose the earliest missing real-runner step rather than jumping to later phases.
2. Preserve the original command boundary and add the smallest real runner that can produce verifiable artifacts for that EID.
3. Use TDD:
   - write a fixture-backend test that fails while the command still emits `gaas_loop.planned_command.v1`;
   - implement the real runner behind the existing CLI name;
   - keep a deterministic fixture backend for fast tests;
   - run the targeted test, then the full relevant test suite.
4. Run the real bounded formal command with `cs_bash_exec` and validate artifacts from disk, not only stdout.
5. Write run summary JSON/MD, record `cs_record_main_experiment`, then record a milestone and route decision.
6. Patch handoff/command docs so future agents know which subcommand is no longer just a recorder.

## Validation checklist

A real-runner backfill is not complete until the run summary states:

- `planned_not_executed: false`
- a positive real-execution field such as `real_forward_pass_executed: true`
- backend name and model IDs
- count and paths for all produced manifests
- artifact-existence checks for each expected output
- caveats that limit interpretation

For trajectory extraction, verify each trajectory manifest plus hidden/logits/token-mask/KV metadata artifacts. If the current split manifest contains only document/shard IDs and no raw corpus text, label any synthetic/provenance prompt as a validation scaffold, not paper-scale corpus extraction.

## Transformers KV-cache pitfall

Modern `transformers` may return `DynamicCache` rather than a tuple. It may be non-subscriptable and may contain per-layer tuples with trailing `None` entries. Do not assume `for layer in outputs.past_key_values: [list(x.shape) for x in layer]` is safe.

Robust pattern:

```python
def past_key_value_shapes(past_key_values):
    if past_key_values is None:
        return []
    if hasattr(past_key_values, "to_legacy_cache"):
        past_key_values = past_key_values.to_legacy_cache()
    shapes = []
    for layer in past_key_values:
        if layer is None:
            shapes.append(None)
        elif hasattr(layer, "shape"):
            shapes.append(list(layer.shape))
        else:
            shapes.append([None if item is None else list(item.shape) for item in layer])
    return shapes
```

Add a regression test for `None` entries before fixing this class of failure.

## Reporting caveat

A bounded real-runner backfill can prove real model forward and artifact writing, but it is not automatically evidence for later claims such as Phase 2 retrofit, adapter training, `Y_recover`, downstream eval, or G2. State this explicitly in milestones and final replies.
