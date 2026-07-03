# PF-REAL-009 Delegation Child Contract Repair Plan

> **For Hermes:** Implement directly with small patches, then run focused/source/installed verification and restart the real-run clean count after reinstall.

**Goal:** Make installed Ponder-Forge `delegations` produce child contexts that are sufficient for real child agents to return parent-submittable JSON reports without hidden gate blockers or duplicated evidence instructions.

**Architecture:** Patch the existing delegation output seam. Keep the CLI and storage shape unchanged. Add compact child report contract text, profile-specific material-claim guidance, role-duty lines, and duplicate-context filtering.

**Design audit:** `worknotes/tmp_pf_real_009_delegation_contract/02_design_audit.md`; it selects the existing `delegation.py` owner seam and rejects new tool surfaces.

**Tech Stack:** Python stdlib, existing pytest suite, installed CLI smoke.

**Plan status:** complete after reread/check. **Confidence:** 100% for this focused repair plan after structural checks pass.

---

## Task 1: Add RED delegation contract tests

**Objective:** Prove the Round 1 child-context defect at the source test seam.

**Files:**
- Modify: `tests/test_prepare_delegations.py`

**Design refs:** B1, B2, B3, B4, B6; D1-D4; C1-C2.

**Steps:**

1. Extend `test_prepare_delegations_exposes_analysis_metric_command_requirement` or add a new test for analysis profile.
2. Assert every analysis child context contains:
   - `"assertions"`
   - `"evidence"`
   - `"artifacts"`
   - `assertion_type`
   - `data_result`
   - `critical`
   - `metric_output`
   - `command`
   - `exit_code`
   - `reproduction_log` or `transform_script`
   - exactly one `Required evidence types:` occurrence
3. Add a role-duty assertion for `data_inspector` and `metric_analyst` contexts.
4. Run:
   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_delegations.py -q
   ```
   Required before implementation: failure on missing contract/duplicate evidence.

## Task 2: Patch `delegation.py` owner seam

**Objective:** Generate child contexts that carry the full minimal report contract.

**Files:**
- Modify: `delegation.py`

**Design refs:** B1-B4,B6; D1-D4; C1-C2.

**Steps:**

1. Add a compact `_report_contract(profile_id)` helper with a JSON skeleton in text form.
2. Expand `_profile_gate_guidance("analysis")` with `data_result`, `critical`, evidence group, and `metric_output.command`/`exit_code` wording.
3. Add `_role_guidance(profile_id, role)` for known role duties.
4. Add duplicate filtering when appending `task.context`; skip it when it matches the generated required-evidence line.
5. Keep `delegate_task_payload` shape unchanged: each task remains `{goal, context, role}`.

## Task 3: Patch bundled skill narrowly

**Objective:** Give manual parent/controllers the same child-report contract without reintroducing direct-tool wording.

**Files:**
- Modify: `resources/skills/ponder-forge-usage/SKILL.md`

**Design refs:** B5; D5; C3.

**Steps:**

1. Add a short `Child report contract` section after report submission instructions.
2. Include the same compact JSON skeleton and explain that children must not call the CLI.
3. Do not mention `ponder_forge_` direct tools.

## Task 4: Run source verification and redundancy review

**Objective:** Prove the source fix and remove excess wording.

**Files:**
- Read: `delegation.py`
- Read: `SKILL.md`
- Modify: `worknotes/note.md`
- Modify: `worknotes/problems.md`

**Commands:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_delegations.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
python3 -m compileall -q .
```

Required: all pass. Then run a small source payload inspection and confirm no duplicate evidence line.

## Task 5: Reinstall and verify installed behavior

**Objective:** Prove the user-facing installed plugin has the fixed contract.

**Files:**
- Modify: `worknotes/note.md`
- Modify: `worknotes/problems.md`

**Commands:**

```bash
python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
python3 -m compileall -q .
```

Run installed fresh CLI start/plan/delegations in a temp `HERMES_HOME` or isolated real-run validation and parse the first child context. Required:

- `has_json_skeleton=True`
- `has_data_result_hint=True`
- `has_critical_hint=True`
- `required_evidence_occurrences=1`
- role duty present for analysis roles

## Task 6: Resume real loop after fix

**Objective:** Restart clean-round counting after PF-REAL-009.

**Files:**
- Modify: `worknotes/note.md`
- Modify: `worknotes/problems.md`

**Steps:**

1. Mark PF-REAL-009 closed only after installed real validation passes.
2. Continue Round 1 as a defect-discovery run, not a clean pass.
3. Start a fresh installed real round after the fix and require three full clean rounds after the last fix.
4. Commit and push Ponder-Forge changes after verification.
