# Idea-Spark CLI version

Source: current working tree at `/home/xu/project/autosci-delphi/idea-spark`.

Default mode: CLI-first / skill + CLI. Hermes `idea_spark_*` tools should remain disabled by default; use:

```bash
hermes idea-spark call <operation> --json-file <payload.json>
```

Local marker: `config.default.json` contains `{ "tools": { "enabled": false } }`. This file is documentation for this snapshot and does not mutate `~/.hermes/idea-spark/config.json`.
