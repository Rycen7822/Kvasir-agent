# Delphi

Delphi is maintained in [Kvasir-agent](https://github.com/Rycen7822/Kvasir-agent)
under `delphi/`. Its original Git history is preserved in this repository.

- [Idea-Spark](idea-spark/README.md): discussion state and shared research ledger.
- [Ponder-Forge](ponder-forge/README.md): complete FrontierAgent high/max team
  strategies, with max as the default and execution owned by the native host.

Use the component documentation for installation and CLI usage. Temporary work
and migration notes belong in the top-level `.work/` directory.

## Tests

Run each suite from its component directory. Idea-Spark's documentation and
manifest tests use component-relative paths.

```sh
cd delphi/idea-spark
python3 -m pytest -q tests
```

Use `delphi/ponder-forge` as the working directory for the Ponder suite.
