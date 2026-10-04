# PF-REAL-005 Repair Plan

规划文档状态：全部完成。
事实信心：100%。真实失败来自 hidden gate contract，而不是 Stage10 evidence 本身。最小修复是把已有 gate rule 暴露给 child prompt，并让 gate gap 明确说明缺失字段。

## Goal

让 analysis profile 子 agent 在提交前知道 `metric_output` evidence 必须包含 `command`，并让 gate blocked 输出直接指出 `metric_output.command` 缺失。

## Architecture

- `delegation.py` owns child instruction payload；在这里加入 profile-specific gate guidance。
- `gates.py` owns gate diagnostics；在这里从 boolean profile-specific check 改为 gap reason。
- `profiles.py` 不扩 dataclass，避免过度设计。
- `schemas.py` 不扩复杂 JSON schema，因为当前工具有意 `additionalProperties=true`。

## Implementation tasks

1. Add RED coverage in `tests/test_prepare_delegations.py`:
   - analysis run prepared context contains `metric_output` and `command` guidance.
2. Add RED coverage in `tests/test_gates_profiles.py`:
   - analysis evidence with `metric_output` but no command blocks and gap includes `metric_output.command`.
3. Implement `_profile_gate_guidance(profile_id)` in `delegation.py` and include returned lines in context.
4. Implement `_profile_specific_gap(profile, evidence)` in `gates.py` and attach `profile_specific_reason` to the gap when present.
5. Verify focused/full tests, reinstall, and restart Round 2 from a fresh run.

## Acceptance gates

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_delegations.py tests/test_gates_profiles.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge
```

## Confidence review

No hidden ambiguity remains. The requirement already exists in `gates.py`; the fix only makes it visible and diagnosable.
