# Early manifest validation notes

Session-derived pattern for DeepScientist early experiment execution.

## Problem

A formal experiment command document may describe pass conditions in conceptual terms (`C != empty`, traceability over `T_F` and `executed_depth`) while the generated artifacts expose those fields through a concrete schema (for example `c` plus `validity_flags=["C_nonempty", ...]`). A literal string check against summary prose can falsely fail even when the manifest is valid.

## Recommended approach

1. Parse the primary manifest, not only the summary markdown.
2. Validate required fields against the actual JSON/JSONL schema.
3. Treat generated summary files as human-facing summaries; if they omit traceability fields that exist in the manifest, append an audit section or create a sidecar summary.
4. Write a final validation JSON/MD with:
   - runstamp
   - bash session ids
   - output paths
   - hashes for locked manifests
   - pass/fail checks
   - baseline gate note
5. Record a milestone only after disk-level validation passes.

## Example checks

Resource preflight:

- `resource_manifest.lock.json` exists
- `all_models_config_present == true`
- `all_models_tokenizer_config_present == true`
- `all_models_have_weights == true`
- SHA256 captured

Split manifest:

- JSON parses
- `no_overlap_verified == true`
- records are nonempty
- records include `dataset_family`, `dataset_name`, `data_split_name`, `document_hash_or_shard_id`, `domain_group`, `answer_span_excluded`, `streaming_route`, `local_metadata_path`

Floorplan manifest:

- JSONL parses
- records are nonempty
- records include `model_id`, `L`, `p`, `q`, `r`, `T_F`, `c`, `executed_depth`, `candidate_set`, `validity_flags`, `floorplan_id`, `mode`
- for `candidate_set == "F_main"`, require integer `c > 0` and `"C_nonempty" in validity_flags`

## Reporting caution

If the user requests "0~3", inspect whether that means document headings 0-3 or experiment identifiers E00-E03. When safe and bounded, execute both the heading setup and preparatory E00-E03 manifests, then state that broader interpretation explicitly.
