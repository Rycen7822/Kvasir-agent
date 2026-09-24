# Evidence file contracts

Files are JSON objects with `schema_version: 1`. Unknown fields are rejected. Paths resolve inside the explicit project; parent traversal and symlink escapes are rejected. Read only the contract needed for the operation:

| Contract | Example | Schema |
| --- | --- | --- |
| Environment | [example](specs/environment.example.json) | [schema](specs/environment.schema.json) |
| RunSpec | [example](specs/run.example.json) | [schema](specs/run.schema.json) |
| CheckSpec | [example](specs/check.example.json) | [schema](specs/check.schema.json) |
| ImportManifest | [example](specs/import.example.json) | [schema](specs/import.schema.json) |

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
