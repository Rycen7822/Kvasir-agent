# PF-REAL-001 Repair Plan

规划文档状态：全部完成。
事实信心：100%。该计划只修复一个已真实触发的 Hermes tool dispatch 兼容缺陷，证据来自当前插件注册代码、当前 tool handler 签名、Hermes core handler 例子和缺失的注册测试断言。

## Goal

让 Ponder-Forge 注册到 Hermes 的所有 public tool handlers 接受 Hermes runtime 传入的 metadata kwargs，例如 `task_id`，同时保持现有内部 handler 合约不变。

## Architecture decision

修复点在插件注册 seam：`__init__.py` 负责把 Ponder-Forge 内部一参数 handler 适配成 Hermes runtime 可调用 handler。不要把 `**kwargs` 扩散到每个业务 tool handler，也不改 `tools.py` 的内部合约。

## Files

- Modify: `__init__.py`
- Modify: `tests/test_plugin_registration.py`
- Update after verification: `worknotes/problems.md`, `worknotes/note.md`

## Tasks

### Task 1 — Add registration adapter

Objective: wrap each `HANDLERS[name]` at registration time.

Implementation:

- Add helper `_hermes_tool_handler(handler)` in `__init__.py`.
- Returned wrapper signature: `def _wrapped(args=None, **_kwargs)`.
- Wrapper returns `handler(args)`.
- Register `handler=_hermes_tool_handler(HANDLERS[name])`.

Proof:

- Existing source tests still pass because internal `HANDLERS` are unchanged.
- New registration test proves live-style metadata kwargs are accepted.

### Task 2 — Add regression test

Objective: prevent this real live failure from returning.

Modify `tests/test_plugin_registration.py`:

- In `test_registered_tool_handlers_return_json_until_full_workflow_lands`, call every registered handler twice:
  - `handler({})`
  - `handler({}, task_id="synthetic-task", tool_call_id="synthetic-call")`
- Assert both return JSON dicts containing `success`.

### Task 3 — Verify, reinstall, rerun real trigger

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_plugin_registration.py tests/test_tools_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge
```

Then call the real native `ponder_forge_start` tool again in the current Hermes session. If current-session tool handler remains stale after reinstall, record that as a current-session reload boundary and verify with a fresh-process plugin registration smoke from the installed path.

## Anti-overdesign decisions

- No new plugin tool.
- No schema change.
- No migration.
- No broad compatibility layer.
- No Hermes core change.
- No changes under the real quest path.

## Acceptance gate

PF-REAL-001 is closed only when a native or fresh-process Hermes-style handler invocation accepts metadata kwargs and returns structured JSON instead of raising `TypeError`.
