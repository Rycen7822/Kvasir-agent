# Manual maintenance

These commands are for an explicit terminal action or a user-supplied manual. They are not MCP tools, default skill dependencies, startup hooks or error-retry instructions. No operation edits AGENTS.md or creates a Codex project note.

## Create minimal state

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /absolute/plugin/path/scripts/ka_admin.py init --project /absolute/existing/project
```

The manual is `manual/init/SKILL.md`, outside the registered `skills/` root. Users may supply that path explicitly if they want Codex to perform the command. It is not a discoverable `$skill` entry. Direct terminal execution uses no model context; explicitly reading the manual uses context in that conversation. Repeating initialization leaves the stable identity and file mtimes unchanged. `scripts/init_project.sh /absolute/project` delegates to the same CLI and creates no model instructions.

## Migrate older state

Stop old writers before planning. Place the plan outside the research state tree:

```sh
python3 /absolute/plugin/path/scripts/ka_admin.py migrate --project /absolute/project --plan-out /absolute/project/migration-plan.json
python3 /absolute/plugin/path/scripts/ka_admin.py migrate --project /absolute/project --apply-plan /absolute/project/migration-plan.json
```

Inspect the plan's sources, hashes, conflicts, run ID/path mappings and unclassified files. Application revalidates inputs. Conflicts stop it before copying. Original files are archived byte-for-byte; old control state stays inactive. Existing source documents remain in place; the replaced root manifest is preserved in the archive. Converted records remain `legacy_unverified`.

An interrupted application leaves `migrations/pending.json`; rerun the same apply command to resume. A changed source or conflicting target fails closed and must be reviewed. Future manifest versions and corrupt metadata are not guessed. Empty legacy directories are reported as cleanup candidates and are not deleted automatically.

## Repair or reconcile

```sh
python3 /absolute/plugin/path/scripts/ka_admin.py repair-events --project /absolute/project
python3 /absolute/plugin/path/scripts/ka_admin.py reconcile --project /absolute/project --run-id RECORDED_ID
```

Event repair preserves a backup and removes invalid lines only when explicitly invoked. Reconcile retries result/event derivation after a run ends; interrupted runs stay interrupted. Running processes are not silently restarted. Generic `ka_native_cli.py` and `kactl.py` handler dispatch has been retired and returns a structured error.
