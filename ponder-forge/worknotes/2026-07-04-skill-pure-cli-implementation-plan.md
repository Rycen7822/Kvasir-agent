# Ponder-Forge Skill + Pure CLI Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Convert Ponder-Forge into a true skill + pure CLI workflow so the installed plugin exposes zero model-visible Ponder-Forge tools and zero hooks by default.

**Architecture:** Keep the existing SQLite-backed core modules (`store.py`, `planner.py`, `delegation.py`, `report_ingest.py`, `verifier.py`, `gates.py`, `renderer.py`) as the owning workflow logic. Add a stdlib `cli.py` that calls those modules directly and returns JSON. Rewrite plugin registration and bundled skill so Hermes users operate Ponder-Forge through terminal CLI commands, not model-visible tools.

**Design audit:** `worknotes/tmp_skill_pure_cli_plan/design_audit.md`. Baseline rows B1-B8 identify the current 9-tool/6-hook public surface; decisions D1-D6 add CLI, remove public registration, rewrite command/skill/tests, and delete obsolete adapter files; compression rows C1-C6 prevent append-only bridge tools and remove dead adapters.

**Tech Stack:** Python stdlib (`argparse`, `json`, `sys`, `pathlib`), existing Ponder-Forge Python modules, pytest, Hermes plugin copied install under `/home/xu/.hermes/plugins/ponder_forge`.

**Repository policy:** Do not commit during execution unless the user explicitly authorizes it. Replace per-task commit steps with `git diff --check`, focused tests, and `note.md` updates.

---

## Task 1: Add RED tests for pure CLI and zero tool/hook registration

**Objective:** Prove the desired public contract fails on the current implementation before changing production code.

**Design refs:** B1, B2, B4, B8; D1, D2, D5; C1, C2, C5.

**Why this is not append-only:** The tests describe the replacement public contract and prevent preserving the obsolete tool surface.

**Files:**
- Create: `tests/test_cli_contract.py`
- Modify: `tests/test_plugin_registration.py`
- Modify: `tests/test_copy_install_smoke.py`

**Step 1: Add CLI workflow test**

Create `tests/test_cli_contract.py` with a subprocess helper that runs `python cli.py ...` against a temp `HERMES_HOME`. Cover:

```python
result = run_cli(tmp_path, "start", "--goal", "research source notes", "--profile", "auto")
assert result["success"] is True
assert result["profile"] == "research"
plan = run_cli(tmp_path, "plan", "--run-id", result["run_id"])
assert plan["success"] is True
payload = run_cli(tmp_path, "delegations", "--run-id", result["run_id"])
assert payload["delegate_task_payload"]["tasks"]
```

Then submit a report using a JSON file, verify, gate, finalize, and assert completed-run late report rejection through the CLI.

**Step 2: Update registration expectations to RED**

In `tests/test_plugin_registration.py`, change expected plugin registration to:

```python
assert ctx.tools == []
assert ctx.hooks == []
assert [command["name"] for command in ctx.commands] == ["ponder-forge"]
assert [skill["name"] for skill in ctx.skills] == ["ponder-forge-usage"]
```

Assert manifest has no listed `ponder_forge_*` tools and no hook names.

**Step 3: Update install-smoke expectation to RED**

In `tests/test_copy_install_smoke.py`, expect:

```python
assert payload["tool_count"] == 0
assert payload["hook_count"] == 0
assert payload["command_count"] == 1
assert payload["skill_count"] == 1
assert (target / "cli.py").exists()
```

**Step 4: Run RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cli_contract.py tests/test_plugin_registration.py tests/test_copy_install_smoke.py -q
```

Expected: FAIL. Current code has no `cli.py`, still registers 9 tools / 6 hooks, and copy smoke still reports old counts.

**Step 5: Reflection / note update**

Update `worknotes/note.md` with RED result and confidence gaps. No commit.

---

## Task 2: Implement the minimal pure CLI

**Objective:** Add `cli.py` as the new public workflow surface over existing core modules.

**Design refs:** B4; D1; C2.

**Why this is not append-only:** CLI uses existing owner modules directly; it does not add a bridge tool or duplicate graph/gate logic.

**Files:**
- Create: `cli.py`
- Test: `tests/test_cli_contract.py`

**Step 1: Write `cli.py` imports and JSON helpers**

Use relative imports when loaded as a plugin package and fallback imports when executed as `python cli.py` from the installed directory:

```python
try:
    from .delegation import prepare_delegations
    from .gates import evaluate_gate, supported_critical_assertion_ids
    from .planner import plan_run
    from .profiles import select_profile
    from .reconcile import reconcile_run
    from .renderer import render_final_report
    from .report_ingest import ingest_report
    from .store import PonderForgeStore
    from .verifier import verify_run
except ImportError:
    from delegation import prepare_delegations
    from gates import evaluate_gate, supported_critical_assertion_ids
    from planner import plan_run
    from profiles import select_profile
    from reconcile import reconcile_run
    from renderer import render_final_report
    from report_ingest import ingest_report
    from store import PonderForgeStore
    from verifier import verify_run
```

Implement `_store()`, `_ok()`, `_err()`, `_emit()`, `_load_json_file()`, and `_final_artifact_paths()`.

**Step 2: Implement subcommand functions**

Implement functions with these names and behavior:

- `cmd_start(args)`: create run; output `next_command: "plan"`.
- `cmd_plan(args)`: call `plan_run`.
- `cmd_delegations(args)`: call `prepare_delegations`.
- `cmd_submit_report(args)`: load JSON from `--file`; reject completed runs; call `ingest_report`; update task status when `task_id` present.
- `cmd_status(args)`: counts rows and evaluates gate.
- `cmd_verify(args)`: build payload from CLI args and optional `--file`; call `verify_run`.
- `cmd_gate(args)`: call `evaluate_gate`.
- `cmd_finalize(args)`: idempotent finalize; gate first; update accepted assertions; call `render_final_report`.
- `cmd_reconcile(args)`: call `reconcile_run`.

**Step 3: Implement argparse**

Subcommands and required args:

```text
start --goal TEXT [--profile auto] [--constraint TEXT repeated]
plan --run-id ID
delegations --run-id ID
submit-report --file PATH
status --run-id ID
verify --run-id ID [--mode precheck|independent_review] [--target-id ID] [--verdict accept|reject|revise] [...]
gate --run-id ID
finalize --run-id ID
reconcile --run-id ID [--stale-after-seconds N]
```

`--file -` reads stdin.

**Step 4: Run CLI contract test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cli_contract.py -q
```

Expected: PASS for CLI behavior, while registration tests may still fail until later tasks.

**Step 5: Reflection / note update**

Reread `cli.py`. Confirm it does not duplicate planner/gate/render logic. Update `note.md` with confidence status. No commit.

---

## Task 3: Rewrite plugin command to CLI-first guidance

**Objective:** Make `/ponder-forge` useful without referencing hidden Ponder-Forge tools.

**Design refs:** B5; D3; C3.

**Why this is not append-only:** The existing command owner is rewritten instead of adding another command.

**Files:**
- Modify: `commands.py`
- Test: `tests/test_plugin_registration.py`

**Step 1: Replace old `tools.py` import**

`commands.py` must import from `cli.py` or directly from the same core helpers. Prefer importing `start_run` or `run_start` helper from `cli.py` so start semantics stay single-owned.

**Step 2: Return CLI next action**

The command output must include:

```json
{
  "success": true,
  "run_id": "...",
  "instruction": "Use terminal: python3 ${HERMES_HOME:-$HOME/.hermes}/plugins/ponder_forge/cli.py plan --run-id ..."
}
```

It must not contain `ponder_forge_plan`, `ponder_forge_start`, or other old tool-call guidance.

**Step 3: Run focused command test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_plugin_registration.py::test_slash_command_creates_run_and_cli_next_instruction -q
```

Expected: PASS after tests are updated in Task 4.

**Step 4: Reflection / note update**

Reread `commands.py` and ensure no dynamic import of `tools.py` remains. Update `note.md`. No commit.

---

## Task 4: Remove model-visible tool/hook registration and update manifest/tests

**Objective:** Make installed Ponder-Forge expose zero tools and zero hooks while keeping command and bundled skill.

**Design refs:** B1, B2, B7, B8; D2, D5; C1, C5.

**Why this is not append-only:** This changes the owning registration seam instead of adding a toggle or bridge tool.

**Files:**
- Modify: `plugin.yaml`
- Modify: `__init__.py`
- Modify: `tests/test_plugin_registration.py`
- Modify: `tests/test_copy_install_smoke.py`
- Modify: `scripts/copy_install_smoke.py` only if needed for CLI/command reporting.

**Step 1: Rewrite manifest**

`plugin.yaml` should not list any `ponder_forge_*` tool or hook names. Minimal shape:

```yaml
name: ponder-forge
kind: standalone
version: 0.1.0
description: Verification-centric CLI and skill workflow for complex Hermes tasks.
provides_tools: []
provides_hooks: []
```

**Step 2: Rewrite `register(ctx)`**

`__init__.py` should only import/register:

```python
from pathlib import Path
from .commands import start_ponder_forge_command

SKILL_NAME = "ponder-forge-usage"
COMMAND_NAME = "ponder-forge"

def register(ctx) -> None:
    ctx.register_command(...)
    if skill.exists():
        ctx.register_skill(...)
```

If `ctx` has `register_cli_command`, either register a minimal command or skip it with no failure. Do not import `schemas.py`, `tools.py`, or `hooks.py`.

**Step 3: Update tests**

`tests/test_plugin_registration.py` must assert:

- no tools
- no hooks
- one slash command
- one bundled skill
- command output is CLI-first
- manifest contains `provides_tools: []` and `provides_hooks: []`

**Step 4: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_plugin_registration.py tests/test_copy_install_smoke.py -q
```

Expected: PASS.

**Step 5: Reflection / note update**

Search for stale `ctx.register_tool`, `ctx.register_hook`, and `TOOL_NAMES` references. Update `note.md`. No commit.

---

## Task 5: Rewrite bundled skill to pure CLI workflow

**Objective:** Ensure future agents do not call obsolete direct tools.

**Design refs:** B6; D4; C4.

**Why this is not append-only:** Replace the operator guide in place.

**Files:**
- Modify: `resources/skills/ponder-forge-usage/SKILL.md`
- Modify: `tests/test_mini_cases_static.py` or `tests/test_plugin_registration.py` for static skill checks.

**Step 1: Replace skill instructions**

The skill must instruct:

1. Locate CLI at `${HERMES_HOME:-$HOME/.hermes}/plugins/ponder_forge/cli.py` when installed.
2. Use `python3 <cli.py> start --goal ...`.
3. Use `plan`, `delegations`, native `delegate_task`, child JSON reports, `submit-report --file`, `verify`, `gate`, and `finalize`.
4. Do not call `ponder_forge_start` or other Ponder-Forge direct tools; they are intentionally not exposed.

**Step 2: Add static check**

Add a test that reads the skill file and asserts:

```python
assert "cli.py" in text
assert "submit-report --file" in text
assert "ponder_forge_start" not in text
assert "ponder_forge_plan" not in text
```

**Step 3: Run focused static test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_mini_cases_static.py -q
```

Expected: PASS.

**Step 4: Reflection / note update**

Reread skill text and confirm it is concise and CLI-first. Update `note.md`. No commit.

---

## Task 6: Delete obsolete adapters and rewrite stale child/test guidance

**Objective:** Remove dead code paths that would otherwise invite accidental re-registration.

**Design refs:** B3, B7, B8, B9, B10; D5, D6, D7; C5, C6, C7.

**Why this is not append-only:** Deletes obsolete adapter files after CLI and registration tests cover the behavior.

**Files:**
- Delete: `tools.py`
- Delete: `schemas.py`
- Delete: `hooks.py`
- Delete: `role_policy.py`
- Modify: `delegation.py`
- Modify: `prompts/reviewers/*.md`
- Modify: `scripts/run_mini_benchmark.py`
- Modify: `tests/test_prepare_delegations.py`
- Modify: `tests/test_profile_verifiers.py`
- Modify: `tests/test_verifier_independence.py`
- Modify: `tests/test_hooks_reconcile.py`
- Delete or rewrite: `tests/test_tools_contract.py`

**Step 1: Remove obsolete files**

Delete `tools.py`, `schemas.py`, `hooks.py`, and `role_policy.py` only after Tasks 2-5 have focused tests passing and direct-tool guidance has been rewritten.

**Step 2: Rewrite child/reviewer guidance**

Change `delegation.py` and `prompts/reviewers/*.md` so children and reviewers return structured JSON in their final answer. The parent/controller submits that JSON with:

```bash
python3 "$PF_CLI" submit-report --file <report.json>
```

No prompt or delegation context should instruct a child to call a Ponder-Forge direct tool.

**Step 3: Replace old direct tool tests and scripts**

Either delete `tests/test_tools_contract.py` or rewrite it to test CLI command equivalence. Preferred: delete it if `tests/test_cli_contract.py` fully covers start/plan/report/verify/gate/finalize/late rejection.

Rewrite `tests/test_prepare_delegations.py`, `tests/test_profile_verifiers.py`, `tests/test_verifier_independence.py`, `tests/test_hooks_reconcile.py`, and `scripts/run_mini_benchmark.py` to use `cli.py` or core modules, not `tools.py`/`hooks.py`/`schemas.py`.

**Step 4: Search for stale imports/guidance**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
root=Path('.')
needles=['from .tools','from tools','from .schemas','from schemas','from .hooks','from hooks','TOOL_NAMES','HOOK_NAMES','ponder_forge_start','ponder_forge_plan','ponder_forge_report_submit','ponder_forge_verify']
for path in root.rglob('*'):
    if 'worknotes' in path.parts or '__pycache__' in path.parts:
        continue
    if path.is_file() and path.suffix in {'.py','.md','.yaml'}:
        text=path.read_text(encoding='utf-8', errors='ignore')
        hits=[n for n in needles if n in text]
        if hits:
            print(path, hits)
PY
```

Expected: no production, manifest, bundled skill, or active test references to deleted adapters or direct tool guidance. Worknotes are excluded because they intentionally preserve historical design evidence.

**Step 5: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cli_contract.py tests/test_plugin_registration.py tests/test_copy_install_smoke.py tests/test_prepare_delegations.py tests/test_profile_verifiers.py tests/test_verifier_independence.py tests/test_hooks_reconcile.py tests/test_mini_cases_static.py -q
```

Expected: PASS.

**Step 6: Reflection / note update**

Reread `__init__.py`, `commands.py`, `cli.py`, and skill file. Update `note.md` with deletion result and confidence. No commit.

---

## Task 7: Source-level landing verification

**Objective:** Prove source tree is internally consistent before installed-copy promotion.

**Design refs:** all D rows; all C rows.

**Why this is not append-only:** This validates the replacement contract and deletion cleanup together.

**Files:**
- No intended code changes unless tests expose a defect.
- Modify: `worknotes/note.md` with verification results.

**Step 1: Run full source tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
```

Expected: all tests pass.

**Step 2: Run compileall**

Run:

```bash
python3 -m compileall -q .
```

Expected: no output, exit 0.

**Step 3: Run stale-reference scan**

Run the scan from Task 6 again, plus:

```bash
git diff --check -- ponder-forge
```

Expected: no whitespace errors and no stale production references.

**Step 4: Reflection / note update**

If any failure occurs, patch root cause and repeat focused test first, then full source tests. Update `note.md`. No commit.

---

## Task 8: Installed-copy verification

**Objective:** Prove the normal user-facing installed plugin path works and exposes zero tools/hooks.

**Design refs:** D1, D2, D4, D5; C1, C2, C4, C5.

**Why this is not append-only:** Validates the actual installed deployment shape, not just source imports.

**Files:**
- No source changes unless install verification fails.
- Installed copy target: `/home/xu/.hermes/plugins/ponder_forge`

**Step 1: Copy install**

Run:

```bash
python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge
```

Expected JSON includes:

```json
{"installed": true, "is_symlink": false, "tool_count": 0, "hook_count": 0, "command_count": 1, "skill_count": 1}
```

**Step 2: Installed-copy tests**

Run:

```bash
cd /home/xu/.hermes/plugins/ponder_forge
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
python3 -m compileall -q .
```

Expected: tests pass and compileall exits 0.

**Step 3: Installed CLI smoke**

Run a temp-home smoke:

```bash
TMP_HOME=$(mktemp -d)
HERMES_HOME="$TMP_HOME" python3 /home/xu/.hermes/plugins/ponder_forge/cli.py start --goal "research source notes" --profile auto
```

Expected: JSON `success=true`, `profile=research`, and a `run_id`.

**Step 4: Reflection / note update**

Compare source and installed hashes for `cli.py`, `__init__.py`, `commands.py`, skill file, and tests. Update `note.md`. No commit unless separately authorized.

---

## Task 9: Final closeout checks

**Objective:** Confirm planning and implementation are complete, and state exact confidence boundaries.

**Design refs:** all rows.

**Files:**
- Modify: `worknotes/note.md`
- Optional modify: `worknotes/problems.md` only if new defects were found.

**Step 1: Reread plan, design audit, and note**

Run `read_file` on:

- `worknotes/2026-07-04-skill-pure-cli-implementation-plan.md`
- `worknotes/tmp_skill_pure_cli_plan/design_audit.md`
- `worknotes/note.md`

Expected: note status matches implemented state; no stale “not complete” remains in the final closeout section.

**Step 2: Git status scope check**

Run:

```bash
git status --short -- ponder-forge | sed -n '1,200p'
```

Expected: only Ponder-Forge files changed.

**Step 3: Final confidence review**

Answer internally:

- Did default installed plugin expose zero model-visible Ponder-Forge tools? Must be yes with installed smoke output.
- Did default installed plugin expose zero hooks? Must be yes with installed smoke output.
- Is the workflow still available through pure CLI? Must be yes with source and installed CLI tests/smoke.
- Are deleted adapters free of stale imports? Must be yes with search output.
- Were no quest files modified? Must be yes; no commands should write quest path.

**Step 4: Final response**

Report:

- plan path
- design artifact path
- files changed/deleted
- validation commands and outputs
- installed-copy status
- residual risks or no residual known implementation gaps

No commit/push unless user explicitly asks.
