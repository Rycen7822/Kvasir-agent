# Migration

Codex-Scientist migration uses `scripts/csctl.py` and remains `codex-native-cli`; it is not MCP.

## Migrate legacy quests

Run from the target project root:

```bash
python scripts/csctl.py migrate legacy-quests --format json
```

The `migrate legacy quests` command scans `DeepScientist/quests/*` for legacy `quest.yaml` or `quest.json` metadata, creates `DeepScientist/research.yaml` when no upgraded manifest exists, and writes `DeepScientist/migrations/migration_report.json`.

Migration is conservative:

- source quest directories are preserved;
- existing notes and artifacts are not deleted;
- the migration report records `source_preserved=true`;
- follow-up validation should run `scripts/csctl.py manifest validate --format json`.

## Long-run follow-up

After migration, run the accelerated soak:

```bash
python scripts/csctl.py soak accelerated --days 10 --inject-failures --format json
```

If the generated validation report still says `wall-clock: not_run`, do not claim stable ten-day wall-clock operation. The real wall-clock soak must be scheduled and recorded separately before release claims.
