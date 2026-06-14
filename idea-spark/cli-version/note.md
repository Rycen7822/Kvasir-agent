# Idea-Spark Development Notes

## Current status

- Plan completion status: `plan.md` exists and has final confidence record.
- Implementation completion status: not complete. No source/test/docs package existed before this development pass.
- Active requirement: implement under `/home/xu/project/autosci-delphi/idea-spark` according to `plan.md`, avoid over-design, update this note after each implementation slice, and reflect until the current slice is factually stable.

## Baseline discovered

- Python: 3.12.13
- uv: 0.11.2
- pytest: 9.0.2
- Git branch: `main...origin/main`
- Working tree before implementation: untracked `.gitignore` and `idea-spark/`.
- `idea-spark/reference/` is ignored and remains reference/scratch only.

## Implementation principles for this pass

- Use small patches and focused file writes.
- Tests precede production code for each phase where possible.
- Keep runtime storage/export only; no network, shell, subprocess, dashboard, vector DB, ranking engine, or autonomous scheduler in plugin handlers.
- Keep role/protocol behavior in examples and README, not hardcoded runtime role engines.
- Every phase must end with: targeted tests, redundancy/dead-code check, confidence reflection, and this note updated.

## Phase log

### Inspect

- Completed initial inspection of `plan.md`, environment, and file tree.
- Phase 0 target files: `pyproject.toml`, `README.md`, `idea_spark/__init__.py`, `idea_spark/plugin.yaml`, `idea_spark/schemas.py`, `idea_spark/tools.py`, `tests/test_schema_contract.py`, `tests/test_plugin_registration.py`.

### Phase 0 RED

- Wrote tests first for canonical constants, manifest shape, registration, and placeholder JSON handler behavior.
- Expected first failure: `idea_spark` package and `plugin.yaml` do not exist yet.

### Phase 0 GREEN / reflection

- Added minimal `pyproject.toml`, README stub, `idea_spark/plugin.yaml`, `schemas.py`, `tools.py`, and `__init__.py`.
- Targeted command passed: `python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py -q` -> 4 passed.
- One test assertion was corrected because it treated `provides_tools:` as a forbidden top-level `tools:` field; production code was not changed for that test bug.
- Redundancy scan: no forbidden MVP strings in `idea_spark/`; source files are small and only contain Phase 0 behavior.
- Confidence: 100% for Phase 0. No dead files or premature feature code found.

### Phase 1 RED

- Added temp DB fixture and migration/hash/path contract tests before production store code.
- Expected first failure: `idea_spark.store` and migration SQL are missing.

### Phase 1 GREEN / reflection

- Added `idea_spark/store.py`, `idea_spark/migrations/0001_init.sql`, and migration package marker.
- Targeted command passed: `python3 -m pytest tests/test_store_migrations.py -q` -> 4 passed.
- Phase 0+1 regression passed: `python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py tests/test_store_migrations.py -q` -> 8 passed.
- Redundancy scan: no forbidden advanced MVP strings in `idea_spark/`.
- Store remains limited to path resolution, canonical JSON/hash, bounded lock retry, connection setup, and migration application; no premature business methods were added.
- Confidence: 100% for Phase 1. The only intentional small duplication is `schema_migrations` bootstrap plus migration declaration; it keeps migration checks possible before running migration SQL and does not create extra behavior.

### Phase 2 RED

- Added public room/message/status/round_wait and basic export tests before implementing tool behavior.
- Required behavior: JSON-string handlers, timeout-safe wait, partial-state timeout, message filters, limit cap, zero-state Markdown sections.
- Expected first failure: `idea_spark.tools` still exposes only placeholder handler map, not direct implemented tool functions.

### Phase 2 GREEN / reflection

- Implemented `idea_spark_room_create`, `room_join`, `message_post`, `message_read`, `room_status`, `round_wait`, and zero-state `room_export`.
- Added `idea_spark/export.py` for deterministic report headings.
- Targeted command passed: `python3 -m pytest tests/test_tools_room.py tests/test_export.py -q` -> 6 passed.
- Phase 0+1+2 regression passed: `python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py tests/test_store_migrations.py tests/test_tools_room.py tests/test_export.py -q` -> 14 passed.
- Reflection fix: moved `round_wait` store initialization out of the polling loop to avoid redundant migration checks while waiting.
- Redundancy scan: no forbidden advanced MVP strings in `idea_spark/`. `tools.py` is now the largest file but still only contains public handler glue and shared helper functions; no artifact/gate/open-need business was prematurely implemented.
- Confidence: 100% for Phase 2.

### Phase 3 RED

- Added artifact, relation, status, gate, and open-need tests before implementing those handlers.
- API choices fixed by tests: `parent_links` creates links from existing source artifact to new artifact; gate records create a `GateDecision` artifact so `passes_gate` / `rejected_by_gate` links remain artifact-to-artifact; out-of-range pressure scores are rejected, not clamped.
- Expected first failure: Phase 3 handlers still return `not implemented`.

### Phase 3 GREEN / reflection

- Implemented artifact create/read/link/status, gate record, and need create handlers.
- Gate records create a `GateDecision` artifact to keep gate relations artifact-to-artifact without adding a new relation table.
- Targeted command passed: `python3 -m pytest tests/test_tools_artifacts_gates.py -q` -> 7 passed.
- Phase 0-3 regression passed: `python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py tests/test_store_migrations.py tests/test_tools_room.py tests/test_tools_artifacts_gates.py tests/test_export.py -q` -> 21 passed.
- Reflection fix: changed `_insert_link` to select the row after `insert or ignore`, avoiding stale `lastrowid` on duplicate links.
- Redundancy scan: no forbidden advanced MVP strings in `idea_spark/`.
- Structure review: `tools.py` is 716 lines. This is large, but every block maps to a planned handler or shared validation/helper and no dead module exists. I am not splitting it yet because a split now would add plan-external modules without reducing behavior risk.
- Confidence: 100% for Phase 3.

### Phase 4 RED

- Expanded export tests before implementation: fixed heading order, gate-backed verdict input, lifecycle statuses, open needs, and transcript appendix.
- Expected first failure: current export only renders headings/transcript and does not yet include artifacts, gates, statuses, or needs.

### Phase 4 GREEN / reflection

- Reworked `idea_spark/export.py` to render fixed Markdown sections from artifacts, gates, open needs, and transcript messages.
- Updated `idea_spark_room_export` to read ledger state once and pass structured data into the renderer.
- Added `examples/sample_report.md` as the fixed report sample required by the plan.
- Targeted command passed: `python3 -m pytest tests/test_export.py -q` -> 5 passed.
- Phase 0-4 regression passed: `python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py tests/test_store_migrations.py tests/test_tools_room.py tests/test_tools_artifacts_gates.py tests/test_export.py -q` -> 25 passed.
- Redundancy scan: no forbidden advanced MVP strings in `idea_spark/`.
- Structure review: export-specific formatting is now in `export.py`; no need to split runtime handlers yet.
- Confidence: 100% for Phase 4.

### Phase 5 RED

- Added README/examples contract tests before writing final docs/examples.
- Tests require complete README section order, canonical tool names only, child join-first rule, gate-backed consensus rule, restart/reset docs, and valid delegate_task JSON template.
- Expected first failure: README is still a stub and `examples/ml_idea_review_prompt.md` plus `examples/delegate_task_template.json` do not exist.

### Phase 5 GREEN / reflection

- Replaced README stub with complete install/use/protocol/failure/safety/test/phase-lock documentation.
- Added `examples/ml_idea_review_prompt.md` and `examples/delegate_task_template.json`.
- Targeted command passed: `python3 -m pytest tests/test_examples_contract.py -q` -> 7 passed.
- Phase 0-5 regression passed: `python3 -m pytest tests/test_schema_contract.py tests/test_plugin_registration.py tests/test_store_migrations.py tests/test_tools_room.py tests/test_tools_artifacts_gates.py tests/test_export.py tests/test_examples_contract.py -q` -> 32 passed.
- Documentation scan for forbidden old-name/internal-execution wording only hit `plan.md` constraint text, not README/examples.
- Confidence: 100% for Phase 5.

### Phase 6 verification / reflection

- Added/renamed plugin registration tests for manifest parity and invalid minimal payload behavior.
- Targeted command passed: `python3 -m pytest tests/test_plugin_registration.py -q` -> 4 passed.
- Real Hermes CLI smoke with a temporary `HERMES_HOME` passed: after copying `idea_spark/*` into temp plugins and running `hermes plugins enable idea-spark`, `hermes plugins list --plain --no-bundled` returned `enabled user 0.1.0 idea-spark`.
- Confidence: 100% for Phase 6.

### Phase 7 final verification / reflection

- Full suite passed: `python3 -m pytest tests/ -q` -> 33 passed.
- Compile check passed: `python3 -m compileall -q idea_spark tests`.
- Docs contract script passed: required canonical tools present and forbidden old-name phrases absent from README/examples.
- Forbidden source scan passed: no `elo`, `trueskill`, `reactor`, `dashboard`, `vector`, `compat_alias`, `legacy_alias`, `subprocess`, `requests`, `urllib.request`, or `socket` in `idea_spark/*.py`.
- `.gitignore` now ignores `idea-spark/reference/`, `__pycache__/`, `.pytest_cache/`, and `*.py[cod]`.
- Removed generated `__pycache__` and `.pytest_cache` directories after final tests.
- Final Git state: untracked `.gitignore` and `idea-spark/`; ignored `idea-spark/reference/` only.
- Confidence: 100% for all implemented MVP plan phases.

## Open risks

- No open implementation risks remain for the MVP scope in `plan.md`.
- Post-MVP locked work remains intentionally unimplemented: tournament/Elo, ArtifactReactor scheduling, visualization/dashboard, vector retrieval, and alternate public tool names.
