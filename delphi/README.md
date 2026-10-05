# Delphi

Delphi is maintained in [Kvasir-agent](https://github.com/Rycen7822/Kvasir-agent) under `delphi/`. Its original Git history is preserved in this repository.

- [Idea-Spark](idea-spark/README.md): discussion state and shared research ledger.
- [Ponder-Forge](ponder-forge/README.md): complete FrontierAgent high/max team strategies, with max as the default and execution owned by the native host.

Codex discovers `$kvasir-agent:idea-spark` and `$kvasir-agent:ponder-forge` through the Kvasir plugin. Both load the [native host contract](HOSTS.md) and the component's canonical workflow; no additional MCP tools or model runtime are registered.

```sh
python3 /absolute/plugin/root/delphi/cli.py --state-dir /absolute/project/.kvasir/delphi idea-spark config show
python3 /absolute/plugin/root/delphi/cli.py --state-dir /absolute/project/.kvasir/delphi ponder-forge start --goal "Research question"
```

Use the same state directory in the parent and every worker. Existing Hermes plugin installation and defaults remain available. Pi can use the same CLI and skills; its native host execution is a separate verification step.

Use the component documentation for installation and CLI usage. Temporary work and migration notes belong in the top-level `.work/` directory.

## Tests

Run each suite from its component directory. Idea-Spark's documentation and manifest tests use component-relative paths.

```sh
cd delphi/idea-spark
python3 -m pytest -q tests
```

Use `delphi/ponder-forge` as the working directory for the Ponder suite.
