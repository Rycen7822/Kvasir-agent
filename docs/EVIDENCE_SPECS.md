# Evidence file contracts

Files are JSON objects with an explicit `schema_version`. Existing v1 inputs remain supported; RunSpec and CheckSpec also accept the documented v2 shapes. Unknown fields are rejected. Paths resolve inside the explicit project; parent traversal and symlink escapes are rejected. Read only the contract needed for the operation:

| Contract | Example | Schema |
| --- | --- | --- |
| Environment | [example](specs/environment.example.json) | [schema](specs/environment.schema.json) |
| RunSpec | [example](specs/run.example.json) | [schema](specs/run.schema.json) |
| CheckSpec | [example](specs/check.example.json) | [schema](specs/check.schema.json) |
| ImportManifest | [example](specs/import.example.json) | [schema](specs/import.schema.json) |
| Comparison | [example](specs/comparison.example.json) | [schema](specs/comparison.schema.json) |
| Research record | [example](specs/research.example.json) | [schema](specs/research.schema.json) |
| Progress | [example](specs/progress.example.json) | [schema](specs/progress.schema.json) |
| Cost | [example](specs/cost.example.json) | [schema](specs/cost.schema.json) |

Example digests and run identifiers are placeholders. Calculate actual SHA-256 values from the evaluator and dataset. The service rejects mismatches; never replace expected hashes merely to make a check pass.

## Environment

`baseline.repo_path` is a project directory. Optional `baseline.commit` pins its Git HEAD. `protected_files` and `datasets` each contain at least one hashed file. They are checked before and after execution. `primary_metric` uses `flat_key` or dotted `json_path`, with maximize/minimize direction and optional numeric range. The environment snapshot is stored by digest; there is no separate registration operation.

## RunSpec

`command` is an argv array, not an implicitly evaluated shell string. If a shell is necessary, specify it explicitly. `cwd` is a project directory. `purpose` is baseline or experiment; experiments require `baseline_run_id` for a completed, verified baseline with the identical environment. `method_id` and `seed` identify comparisons. Resources enforce wall-clock timeout and maximum bytes saved per stdout/stderr log; they do not provide GPU allocation or OS sandboxing.

The child receives `KVASIR_RUN_DIR`, `KVASIR_RUN_ID` and `KVASIR_SEED`. Write `metrics_path` and all declared `outputs` under that unique run directory. Output paths are relative to the run, not to project cwd. For example, Python can write `Path(os.environ['KVASIR_RUN_DIR']) / 'metrics.json'`. Control record and log filenames are reserved.

The caller supplies an idempotency key. The persisted request digest includes the specification and environment snapshot. Same key and same digest reuse the original run even after the server restarts; changed requests conflict. An interrupted start is never silently retried. Return receipts use project-relative paths where indicated.

## CheckSpec

Three shapes are supported:

- Environment: `target: environment`, `environment_path`.
- Run: `target: run`, `run_id`.
- Claim: `target: claim`, `claim`, distinct `run_ids`, `minimum_seeds`.

Each shape includes `schema_version`. Claim checks resolve actual records, verify artifact hashes, require comparable environments/methods/baselines and count distinct recorded seeds. Imported or incomplete records cannot establish a verified claim. The report assesses material integrity, not novelty, causal validity, statistical power or scientific truth. Checks write their own report but do not repair evidence.

## ImportManifest

Copy external files into the project first. Supply origin type/source/run identity, environment reference, method/seed, metric path and hashed artifacts. Metrics must be among the hashed artifacts. Imports copy their evidence to a stable directory and always retain `external_unverified` trust. A supplied `trusted` field is rejected. Identical manifests reuse the import and can retry partial result derivation.

## Local trust boundary

Managed evidence records local execution and checked bytes. This is not a sandbox or cryptographic attestation against a project owner or command that deliberately rewrites state. Review commands before authorizing runs. Retain original external provenance; never equate checksum success with independently verified execution.

## Version 2: comparisons and candidates

RunSpec v2 retains the v1 required fields and adds optional comparison, candidate_path, progress_path, cost_path and result_origin. Comparison binds protocol_path, pair_id, metric_unit and metric_selection. These fields describe the actual request; the protocol/candidate snapshots are included in its idempotency digest and checked at worker boundaries. Set result_origin to fresh/cached/replayed/unknown with an optional source_run_id; missing origin is unknown. Declared cached/replayed results cannot count as independent paired samples. Declared seeds do not prove that the program configured its RNG.

Comparison files declare exact environment/data/evaluator, method input hashes, task/seed pairs, metric units/direction/selection and a wall-time timeout budget. This version supports require_all_pairs, unique_valid_attempt and descriptive_only. It does not implement inferential statistics, OS resource quotas or independent preregistration. Protocol timing is prospective/retrospective as declared, with a saved local reference timestamp; do not re-label a post-hoc choice as prior registration.

CheckSpec v2 adds:

- `target: import`, `import_id`: recheck saved copies, mapping and metric even if the original external path is gone; origin remains external_unverified.
- `target: comparison`, `protocol_path`: inspect every managed attempt bound to that protocol digest. Different seeds may reference distinct baseline IDs. Missing/ambiguous pairs, failed attempts, unit/selection/seed/budget mismatches stay explicit; there is no automatic best-run selection.
- `target: research`, `record_ids`: check research revisions and dependencies; see [research records](RESEARCH_RECORDS.md).

Checks separate execution, integrity, comparability, statistical support and review, and retain scientific_validity=not_assessed. Status reads stored facts with integrity_check=not_performed; a saved verified label is not fresh revalidation. Run checks reparse the hashed metric original. Idempotent imports recheck saved targets and report corruption rather than overwrite them. Details remain in report files; MCP summaries are bounded.

## Advisory progress and cost

RunSpec v2 may declare progress_path and cost_path relative to its run directory. Write the matching schema with KVASIR_RUN_ID. Files are read with a 64 KiB limit; missing or invalid observations never set completion or prevent stop. Progress older than 300 seconds is marked stale; heartbeat is not proof of process liveness. Requested/published/applied/serving versions remain separate declarations.

The wrapper records observed managed-process wall seconds. Program cost entries distinguish observed/estimated/unknown and run/search/selected_candidate scope; unknown value must be null. Unreported resources remain unknown. At completion an observation summary/hash snapshot is retained; later changes are visible. Include an observation file in outputs if it must also be part of the required immutable evidence. Full ledgers remain at the returned paths, while status shows at most five entries. Plugin attempt wall totals do not certify complete host/search cost.
