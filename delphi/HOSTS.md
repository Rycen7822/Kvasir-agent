# Native host contract

Delphi supplies discussion/research state and strategies. The host owns models, agent lifetimes, tool access, concurrency, waiting and cancellation.

## CLI and state

Resolve the **installed plugin root** from the skill file; it is not the current research project. Choose one absolute state directory for the project, normally `<project>/.kvasir/delphi`. Do not put research state in the plugin cache.

```sh
python3 /absolute/plugin/root/delphi/cli.py --state-dir /absolute/project/.kvasir/delphi idea-spark call OPERATION --json-file payload.json
python3 /absolute/plugin/root/delphi/cli.py --state-dir /absolute/project/.kvasir/delphi ponder-forge start --goal "..."
```

Component workflow examples abbreviate these full prefixes as `idea-spark` and `ponder`; these are not assumed to be installed shell commands. Every worker must receive the exact absolute prefix, state path, role and scratch directory. Use separate scratch files per concurrent worker. JSON payloads may also use `--stdin` on Idea-Spark. The common CLI makes the explicit state path authoritative over inherited Hermes settings and `IDEA_SPARK_DB`.

Before preparing an unfamiliar payload, use `idea-spark schema OPERATION` to read its existing input schema on demand. Use `ponder COMMAND --help` for Ponder arguments. No Delphi operation schemas are added to the MCP context.

Direct Hermes component commands keep their existing defaults when `DELPHI_HOME` is unset: `hermes idea-spark ...` and the registered Ponder command still work. For a shared custom state root, both component CLIs accept `DELPHI_HOME`.

## Codex

- Read skills and references with native file/terminal tools. `skill_view`, Hermes `delegate_task`, and Hermes toolset arguments are not Codex interfaces.
- Use the native agent tools actually exposed by the session. In Codex V2, spawn creates an agent, followup assigns more work to an existing agent, messages steer work, and waiting receives updates. Follow each tool's real signature; a wait returning is not by itself proof that all workers finished.
- Supply the complete prepared role/context and assignment in the agent's task message. Delphi's `system_prompt` field is text to include, not a supported keyword argument or an override of the host system instructions.
- Preserve any user model restriction for the coordinator and every worker. Do not silently use a faster/different model for a role.
- For Ponder, record an actual start only after a successful native launch; collect the complete native final reply, then record it with `submit-report`. Reuse the same native agent for sequential work by logical role name.
- For Idea-Spark, workers join/read/write the shared ledger directly. The parent checks the persisted phase artifacts, continues r1→r2→r3→r4, and exports only after an actual gate. A worker's final reply is a summary, not the ledger.
- When cancelling, use native cancellation and record its observed outcome. Neither a prepared assignment nor elapsed time proves execution or termination.

## Hermes and Pi

Hermes may use its existing registration, `delegate_task`, skill reader and explicit tool mode. Pi may use the same absolute common CLI and filesystem skills, with the native agent capability available in that installation. This contract does not install a separate agent harness or emulate a missing host agent tool. Pi's installed-host execution is verified separately.
