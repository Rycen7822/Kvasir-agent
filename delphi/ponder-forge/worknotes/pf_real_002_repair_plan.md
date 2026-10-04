# PF-REAL-002 Repair Plan

规划文档状态：全部完成。
事实信心：100%。当前问题是 delegation payload 丢失 run-level context，修复点唯一且明确：`delegation.py` 已经读取 run，因此必须在该 seam 把 `user_goal` 和 `config_json.constraints` 注入 child context。

## Goal

让每个 Ponder-Forge child agent 收到真实任务目标和约束，特别是真实项目路径与只读边界。

## Architecture decision

修复 `prepare_delegations`，不重写 planner。Planner 继续负责创建角色任务；delegation 负责把 run-level context 与 task-level context 合并成 native `delegate_task` payload。

## Files

- Modify: `delegation.py`
- Modify: `tests/test_prepare_delegations.py`
- Update after verification: `worknotes/problems.md`, `worknotes/note.md`

## Tasks

### Task 1 — Include run goal and constraints in child context

Implementation:

- Add local JSON loader helper or reuse narrow inline parsing in `delegation.py`.
- Read `run["user_goal"]`.
- Parse `run["config_json"]` and extract `constraints` if list.
- Add context lines:
  - `Ponder-Forge run goal: ...`
  - `Ponder-Forge constraints:` followed by bullet constraints.

### Task 2 — Add regression coverage

Modify `tests/test_prepare_delegations.py`:

- Start a run with a distinctive goal and constraint.
- Assert every prepared task context contains the goal phrase and constraint phrase.
- Keep idempotency assertion intact.

### Task 3 — Verify and reinstall

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_delegations.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge
```

Then regenerate Round 1 payload from the installed plugin and confirm the quest path and read-only constraint appear in child contexts before dispatching native `delegate_task`.

## Anti-overdesign decisions

- No new schema/migration.
- No new planner roles.
- No prompt engine.
- No broad context templating system.
- No changes under the quest path.

## Acceptance gate

PF-REAL-002 is closed only when the installed plugin generates delegation payloads containing both the real user goal and run constraints.
