---
name: kvasir-agent-manual-init
description: Create minimal project state only when the user explicitly supplies this manual and requests initialization.
---

# Manual project initialization

This file is distributed outside the registered skill directory. It must not be added to skill discovery, main research instructions, dependencies, hooks or default prompts. Do not run it because an ordinary research operation reports missing state.

When the user explicitly requests initialization, use the existing absolute project directory and run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /absolute/plugin/path/scripts/ka_admin.py init --project /absolute/project
```

Resolve the plugin path from this file's location. Do not infer a different project from cwd or environment variables. The command creates only `Kvasir-agent/research.yaml` and the event journal/write lock. It writes no AGENTS.md, Codex notes or skill references. Repeating it preserves identity and mtime. Existing legacy state requires explicit migration; initialization never migrates it.

A user may run the command directly without involving a model. If this file is explicitly loaded in a Codex conversation, its content consumes context in that conversation. No registration policy flag can substitute for keeping it outside automatic discovery.
