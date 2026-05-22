# Migration

Codex-Scientist migration uses the stable curated MCP control plane for repeated validation/status calls and `scripts/csctl.py` CLI fallback for bulk migration, CI, and recovery.

## Migrate legacy quests

Run from the target project root:

```bash
python scripts/csctl.py migrate legacy-quests --format json
```

The `migrate legacy quests` command scans `CodexScientist/quests/*` for legacy `quest.yaml` or `quest.json` metadata. A single legacy quest can be imported into root-bound `CodexScientist/research.yaml`; multiple legacy quests return an explicit migration block instead of selecting a latest or active quest.

Migration is conservative:

- source quest directories are preserved;
- existing root-bound notes and artifacts are not overwritten;
- conflicts are written to `CodexScientist/migrations/migration_conflict_report.json` for operator review;
- successful imports write `CodexScientist/migrations/migration_report.json` with `source_preserved=true` and any `quest_id_mapping`;
- follow-up validation should run `scripts/csctl.py manifest validate --format json`.

After migration, new runtime writes continue to target `<project>/CodexScientist/` directly. `CodexScientist/quests/` remains a legacy input namespace only.

## Long-run follow-up

After migration, run the accelerated soak:

```bash
python scripts/csctl.py soak accelerated --days 10 --inject-failures --format json
```

If the generated validation report still says `wall-clock: not_run`, do not claim stable ten-day wall-clock operation. The real wall-clock soak must be scheduled and recorded separately before release claims.
