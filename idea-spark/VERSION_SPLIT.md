# Idea-Spark preserved versions

This directory intentionally keeps two side-by-side Idea-Spark versions for comparison and validation.

## `cli-version/`

- Source: current working tree at `/home/xu/project/autosci-delphi/idea-spark` at the time this split was created.
- Default mode: CLI-first / bundled skill + CLI command.
- Expected registration smoke: tools `0`, skills `['idea-spark-usage']`, CLI `['idea-spark']`.
- Local marker: `cli-version/config.default.json` contains `{"tools":{"enabled":false}}`.

Use CLI operations such as:

```bash
hermes idea-spark call <operation> --json-file <payload.json>
```

## `toolset-version/`

- Source: requested backup package `/home/xu/backups/autosci-delphi/20260614_171954/idea-spark-working-tree.tgz`.
- Default mode: toolset-oriented old version from the backup.
- Expected registration smoke: tools `14`, skills `['idea-spark-usage']`, CLI `[]`.
- Local marker: `toolset-version/config.default.json` contains `{"tools":{"enabled":true}}`.

## Validation performed

```text
cli-version: pytest -q tests/test_plugin_registration.py -> 6 passed
cli-version registration smoke -> tools=0, skills=['idea-spark-usage'], cli=['idea-spark']

toolset-version: pytest -q tests/test_plugin_registration.py -> 6 passed
toolset-version registration smoke -> tools=14, skills=['idea-spark-usage'], cli=[]
```

The marker config files are documentation for these preserved snapshots. They do not mutate the active Hermes profile config at `~/.hermes/idea-spark/config.json`.
