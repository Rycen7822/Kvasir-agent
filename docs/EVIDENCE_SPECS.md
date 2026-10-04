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

File references require only `path`, with an optional declared `version`. Current schemas and examples have no checksum fields. Old `sha256` and `environment_digest` fields are removed from the loaded document at the compatibility boundary, without rewriting old files or checking their values. IDs and declared versions identify records; they do not prove byte integrity.

## Environment

`baseline.repo_path` is a project directory. Optional `baseline.commit` checks its Git HEAD at launch. `protected_files` and `datasets` each contain at least one declared file reference; the existing field name `protected_files` does not imply byte immutability. Launch checks their paths and existence once. `primary_metric` uses `flat_key` or dotted `json_path`, with maximize/minimize direction and optional numeric range. The environment snapshot is saved under the ordinary run ID; there is no separate registration operation or repeated input hashing.

## RunSpec

`command` is an argv array, not an implicitly evaluated shell string. If a shell is necessary, specify it explicitly. `cwd` is a project directory. `purpose` is baseline or experiment; experiments require `baseline_run_id` for a completed baseline with available metrics and matching declared environment settings. `method_id` and `seed` identify comparisons. Resources enforce wall-clock timeout and maximum bytes saved per stdout/stderr log; they do not provide GPU allocation or OS sandboxing.

The child receives `KVASIR_RUN_DIR`, `KVASIR_RUN_ID` and `KVASIR_SEED`. Write `metrics_path` and all declared `outputs` under that unique run directory. Output paths are relative to the run, not to project cwd. For example, Python can write `Path(os.environ['KVASIR_RUN_DIR']) / 'metrics.json'`. Control record and log filenames are reserved.

The caller supplies an idempotency key. Same key and same RunSpec return the original run even after the server restarts. The original environment/protocol/candidate snapshots stay attached to that run; editing these separate files does not change a retry into another launch. Changing the RunSpec requires a new key. To deliberately run again with edited inputs, also use a new key. An interrupted start is never silently retried. Return receipts use project-relative paths where indicated.

## CheckSpec

Three shapes are supported:

- Environment: `target: environment`, `environment_path`.
- Run: `target: run`, `run_id`.
- Claim: `target: claim`, `claim`, distinct `run_ids`, `minimum_seeds`.

Each shape includes `schema_version`. Claim checks resolve actual records, reparse saved metrics, compare declared environments/methods/baselines and count distinct recorded seeds. Imported or incomplete records cannot establish managed execution. A completed check returns `ok=true` even when its report has `status=failed` and issues; actual read/write or argument failures remain tool errors. Checks do not repair evidence, prove byte integrity or certify scientific truth. Repeat a check only when relevant facts or the question change.

## ImportManifest

Copy external files into the project first. Supply origin type/source/run identity, environment reference, method/seed, metric path and artifact paths. Metrics must be among the artifacts. Imports use ordinary IDs, copy their evidence to a stable directory and always retain `external_unverified` trust. Imports check files and parse the saved metric; copying does not calculate or compare checksums. A supplied `trusted` field is rejected. Identical declared manifests and environment settings reuse the saved import and can retry partial result derivation, even if original artifact paths are gone. Give a new external result a distinct origin run identity; editing a source file does not overwrite a previous import.

## Local trust boundary

Managed evidence records local execution, saved settings, output paths/sizes and parsed metrics. Default status and audits do not certify unchanged bytes. Retain original external provenance and explicit user constraints. Saving a result or verifying a copy does not independently verify its execution or scientific interpretation.

## Version 2: comparisons and candidates

RunSpec v2 retains the v1 required fields and adds optional comparison, candidate_path, progress_path, cost_path and result_origin. Comparison binds protocol_path, pair_id, metric_unit and metric_selection. Protocol/candidate snapshots are saved at launch; history checks use these snapshots without rereading current editable specifications or recursively hashing dependencies. Set result_origin to fresh/cached/replayed/unknown with an optional source_run_id; missing origin is unknown. Declared cached/replayed results cannot count as independent paired samples. Declared seeds do not prove that the program configured its RNG.

Comparison files identify the environment with `environment_id`, and declare dataset/evaluator and method input paths/versions, task/seed pairs, metric units/direction/selection and a wall-time timeout budget. `protocol_id` and optional `version` select the cohort. All attempts in that cohort remain visible; changed substantive protocol settings produce an explicit comparison issue without invalidating the original run. The environment ID is optional for legacy protocols; comparisons still inspect the saved run environment and declared protocol conditions, without claiming an independently verified environment binding. This version supports require_all_pairs, unique_valid_attempt and descriptive_only. It does not implement inferential statistics, OS resource quotas or independent preregistration. Protocol timing is prospective/retrospective as declared, with a saved local reference timestamp.

CheckSpec v2 adds:

- `target: import`, `import_id`: recheck saved copies, mapping and metric even if the original external path is gone; origin remains external_unverified.
- `target: comparison`, `protocol_path`: inspect every managed attempt under that protocol ID/version. Different seeds may reference distinct baseline IDs. Missing/ambiguous pairs, failed attempts, unit/selection/seed/budget mismatches stay explicit; there is no automatic best-run selection.
- `target: research`, `record_ids`: check research revisions and dependencies; see [research records](RESEARCH_RECORDS.md).

Checks separate execution, comparability, statistical support and review, and retain scientific_validity=not_assessed. Byte integrity is `not_assessed` and integrity_check is `not_performed`. New successful metric records use `evidence_status=recorded`; old `verified` labels remain readable without implying fresh integrity verification. Run checks reparse saved metrics and detect missing outputs or mismatched metric values, without hashing every artifact. Idempotent imports check saved mapping, availability and metric consistency rather than overwrite their copies. Details remain in report files; MCP summaries are bounded.

## Advisory progress and cost

RunSpec v2 may declare progress_path and cost_path relative to its run directory. Write the matching schema with KVASIR_RUN_ID. Files are read with a 64 KiB limit; missing or invalid observations never set completion or prevent stop. Progress older than 300 seconds is marked stale; heartbeat is not proof of process liveness. Requested/published/applied/serving versions remain separate declarations.

The wrapper records observed managed-process wall seconds. Program cost entries distinguish observed/estimated/unknown and run/search/selected_candidate scope; unknown value must be null. Unreported resources remain unknown. At completion an observation summary is retained; later status reads return current declared values without hashes or byte-change flags. Writers should atomically replace observation JSON files; an incomplete read is an unavailable observation, not an execution failure. Full ledgers remain at the returned paths, while status shows at most five entries. Plugin attempt wall totals do not certify complete host/search cost.
