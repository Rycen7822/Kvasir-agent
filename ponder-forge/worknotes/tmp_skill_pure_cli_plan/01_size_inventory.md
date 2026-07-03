# Size and Source Inventory

Collected from read-only file reads and `python3` size probe on 2026-07-04T06:11:31+08:00.

| path | exists | bytes | lines | relevance |
|---|---:|---:|---:|---|
| `plugin.yaml` | yes | 528 | 21 | declares 9 tools and 6 hooks |
| `__init__.py` | yes | 2592 | 73 | registers tools, hooks, slash command, bundled skill |
| `schemas.py` | yes | 1871 | 48 | owns `TOOL_NAMES`, `HOOK_NAMES`, and tool schemas |
| `tools.py` | yes | 9204 | 249 | current public handler wrappers around core functions |
| `commands.py` | yes | 1028 | 26 | slash command currently calls `ponder_forge_start` only |
| `hooks.py` | yes | 6310 | 159 | subagent/tool/LLM hooks; adds runtime surface beyond CLI |
| `resources/skills/ponder-forge-usage/SKILL.md` | yes | 957 | 23 | instructs agents to call 9 tools |
| `config.py` | yes | 754 | 29 | `HERMES_HOME`-aware state path owner |
| `store.py` | yes | 18062 | 533 | SQLite durable state owner |
| `planner.py` | yes | 1985 | 54 | creates workflow tasks/nodes |
| `delegation.py` | yes | 2520 | 59 | emits native `delegate_task` payload |
| `verifier.py` | yes | 8505 | 199 | precheck/reviewer/verdict owner |
| `gates.py` | yes | 7456 | 182 | profile gate owner |
| `renderer.py` | yes | 6595 | 164 | final report owner |
| `report_ingest.py` | yes | 8668 | 218 | structured report ingestion owner |
| `tests/test_plugin_registration.py` | yes | 4889 | 146 | currently expects 9 tools / 6 hooks / 1 command / 1 skill |
| `tests/test_tools_contract.py` | yes | 6548 | 169 | tests current direct tool workflow |
| `tests/test_prepare_delegations.py` | yes | 3177 | 79 | tests delegation context guidance |
| `scripts/copy_install_smoke.py` | yes | 3154 | 99 | copies source plugin and reports exposed tool/hook counts |

## Current measured context sink

`schemas.py` advertises 9 model-visible tools. Serialized schema list is ~1928 chars (~482 chars/4 rough tokens). The larger cost is not just schema bytes; it is the permanent tool-choice branch and child-agent visibility of nine Ponder-Forge functions.

## Files likely to modify

- `plugin.yaml`
- `__init__.py`
- `commands.py`
- `resources/skills/ponder-forge-usage/SKILL.md`
- new `cli.py`
- tests under `tests/`
- `scripts/copy_install_smoke.py`
- `worknotes/note.md`, `worknotes/problems.md` if implementation uncovers defects

## Files likely to keep as internal library

- `tools.py` can remain temporarily as internal Python wrapper/compatibility for tests only if not registered as Hermes tools.
- `hooks.py` can remain in the tree initially, but must not be registered. A later cleanup can delete it once no tests/docs rely on hook behavior.
- `schemas.py` should stop being a public plugin contract. It may remain as a compatibility constant module only if tests do not expose it as model-visible.
