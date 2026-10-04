# PF-REAL-003 Repair Plan

规划文档状态：全部完成。
事实信心：100%。当前问题是 final renderer 丢失已存在的 evidence/artifact/verdict trace；修复点唯一是 `renderer.py`，不需要 schema、migration、新 tool、daemon、runner 或复杂模板系统。

## Goal

让 Ponder-Forge final report 成为真实任务可用的 durable artifact：每个 accepted assertion 不只输出一句结论，还输出紧凑 evidence trace、artifact trace 和 independent reviewer verdict trace。

## Architecture

继续使用现有 `render_final_report(store, run_id)` owner seam。SQLite 已存储全部 needed rows：`assertions`、`evidence_items`、`artifacts`、`verification_verdicts`、`reports`、`statement_assertion_links`。Renderer 在写 `final.md` 时从这些 rows 生成 Markdown nested bullets。

## Design decisions

1. **Rewrite existing renderer, not append a new report generator.**
   - File: `renderer.py`
   - Rationale: final output is renderer ownership；新 public tool 会造成重复路径。
2. **Use existing store rows only.**
   - No migration.
   - No new persisted tables.
   - No report schema changes.
3. **Render compact trace.**
   - Evidence line format: `evidence_type: source_ref — observation`.
   - Artifact line format: `artifact_type: path — summary`.
   - Verdict line format: `verdict by reviewer_role (confidence): rationale`.
   - Long text truncated inside renderer to avoid huge reports.
4. **Keep current blocked behavior.**
   - Unlinked material final statements still block.
   - Auto statement creation from accepted assertions remains unchanged.

## Implementation tasks

### Task 1 — Add RED coverage

Modify `tests/test_gates_profiles.py` renderer test so final Markdown must contain:

- an evidence source ref and quote from `evidence_items`;
- an artifact path from report artifacts;
- an independent verifier verdict/rationale.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_gates_profiles.py::test_renderer_blocks_unlinked_final_statement_and_renders_linked_accepted_assertion -q
```

Expected RED before implementation: missing evidence/artifact/verdict text.

### Task 2 — Implement compact trace rendering

Modify `renderer.py`:

- add helper `_evidence_by_assertion(store, run_id)`;
- add helper `_artifacts_by_report(store, run_id)`;
- add helper `_verdicts_by_assertion(store, run_id)`;
- add helper `_clip(value, limit=240)`;
- when rendering a linked accepted assertion under a final statement, append nested `Evidence`, `Artifacts`, and `Verifier verdicts` bullets when available.

### Task 3 — Verify and reinstall

Run focused and broad gates:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_gates_profiles.py tests/test_tools_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge
```

Then re-finalize or start Round 2 to prove installed output contains evidence trace.

## Confidence review

No hidden ambiguity remains. The fix is narrow, owner-seam aligned, and backed by an exact real failure. Overdesign is avoided because the change only projects existing graph rows into the existing Markdown renderer.
