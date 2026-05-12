---
name: codexscientist-scout
description: Compact Codex-Scientist router for codexscientist-scout; use for its research stage while keeping Codex-native operations outside the plugin runtime.
version: 2.0.0
---

# codexscientist-scout compact router

This active skill is intentionally compact. The historical long playbook was moved to `references/legacy-playbook.md` and is reference-only.

## Operating contract

- Codex-Scientist is a Codex CLI plugin, not a standalone autonomous framework.
- Default mode is `copilot`; do not invent, improve, or expand ideas automatically unless the user or project manifest explicitly enables autonomous idea improvement.
- Use Codex-native file search, edits, shell, tests, and git for ordinary development work.
- Use `scripts/csctl.py` only for project-local research state, provenance, queues, trials, summaries, wiki/frontier records, and compact evidence.
- Keep outputs compact. Return paths, ids, hashes, metric values, short tails, and next action; do not paste full logs, full wiki, or full historical playbooks into context.
- Do not execute old API names directly. Translate historical playbook wording to current `csctl` commands.

## Current command surface

Use the relevant subset:

```bash
python scripts/csctl.py manifest validate --format json
python scripts/csctl.py manifest show --format json
python scripts/csctl.py baseline show --format json
python scripts/csctl.py trial show <trial_id> --format json
python scripts/csctl.py runner status --format json
python scripts/csctl.py runner tail <run_id> --limit 80 --format json
python scripts/csctl.py queue status --format json
python scripts/csctl.py wiki query-pack --max-chars 12000 --format json
python scripts/csctl.py frontier select --limit 5 --format json
python scripts/csctl.py journal negative --trial-id <trial_id> --idea-id <idea_id> --failure-reason <reason> --lesson <lesson> --format json
```

## Stage workflow

1. Read `CodexScientist/research.yaml` and `CodexScientist/summaries/context_pack.md` when present.
2. Identify the single next bounded research action for this stage.
3. If stage-specific nuance is needed, read only the relevant section of `references/legacy-playbook.md` and translate it to the current `csctl` surface.
4. Apply manifest, baseline, metric, readonly, budget, and autonomy gates before any trial changes.
5. Record durable outcomes through `csctl` services and keep ordinary code edits in Codex-native operations.

## Legacy reference

`references/legacy-playbook.md` preserves the pre-upgrade detailed playbook for audit and migration. It may contain old names and long procedures. Treat it as source material, not executable instructions.
