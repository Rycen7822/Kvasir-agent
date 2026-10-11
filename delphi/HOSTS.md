# Native host contract

Delphi supplies discussion/research state and strategies. The host owns models, agent lifetimes, tool access, concurrency, waiting and cancellation.

## MCP and state

Use the shared `ka_delphi` MCP tool with an absolute research `project`, explicit `workflow=idea_spark|ponder_forge` and `action`. State is project-bound at `<project>/.kvasir/delphi`. Open selects the Idea-Spark mode or Ponder effort; later calls use the returned room_id/run_id. Native hosts keep agent execution and the parent keeps research decisions.

Read the selected instruction_path once, edit returned input templates and follow next_call. Each prepared worker receives complete instructions and durable output/receipt paths plus a separate `.work` scratch directory. Workers deliver files; the parent collects after actual native completion. No worker needs the ledger CLI prefix or MCP schema. Use fresh request_id values for new open/prepare/verify allocations and the same value for retries; a changed input needs a new ID. Full high/max policies remain intact.

## CLI fallback and maintenance

Resolve the **installed plugin root** from the skill file; it is not the current research project. Choose one absolute state directory for the project, normally `<project>/.kvasir/delphi`. Do not put research state in the plugin cache.

```sh
python3 /absolute/plugin/root/delphi/cli.py --state-dir /absolute/project/.kvasir/delphi idea-spark call OPERATION --json-file payload.json
python3 /absolute/plugin/root/delphi/cli.py --state-dir /absolute/project/.kvasir/delphi ponder-forge start --goal "..."
```

Component workflow examples abbreviate these full prefixes as `idea-spark` and `ponder`; these are not assumed to be installed shell commands. The parent uses the exact absolute prefix and state path for the fallback. Workers receive only their full instructions and assigned files. JSON payloads may also use `--stdin` on Idea-Spark. The common CLI makes the explicit state path authoritative over inherited Hermes settings and `IDEA_SPARK_DB`.

For an unfamiliar fallback payload, use `idea-spark schema OPERATION` or `ponder COMMAND --help`. The default MCP catalog adds only ka_delphi; it does not publish each low-level ledger operation. Configuration, manual init, maintenance and dashboard launch stay in CLI.

Direct Hermes component commands keep their existing defaults when `DELPHI_HOME` is unset: `hermes idea-spark ...` and the registered Ponder command still work. For a shared custom state root, both component CLIs accept `DELPHI_HOME`.

## Codex

- Read skills and references with native file/terminal tools. `skill_view`, Hermes `delegate_task`, and Hermes toolset arguments are not Codex interfaces.
- Use the native agent tools actually exposed by the session. In Codex V2, spawn creates an agent, followup assigns more work to an existing agent, messages steer work, and waiting receives updates. Follow each tool's real signature; a wait returning is not by itself proof that all workers finished.
- Supply the complete prepared role/context and assignment in the agent's task message. Delphi's `system_prompt` field is text to include, not a supported keyword argument or an override of the host system instructions.
- Preserve any user model restriction for the coordinator and every worker. Do not silently use a faster/different model for a role.
- For Ponder, record an actual start only after a successful native launch using action=record. Collect complete files with action=collect; preserve the full native reply at the preallocated path when a write fails. The fallback remains submit-report. Reuse the same native agent for sequential work by logical role name.
- For Idea-Spark, the parent selects `open_discussion` (default) or `deep_exploration`, then uses `files prepare` to allocate a durable output file and receipt per assignment. Workers keep interim notes in their assigned `.work` scratch directory, write the complete report and return the absolute path; a write failure returns the full body. After native completion the parent runs `files collect`, reads the files, and saves phase/next action through `workflow checkpoint`. Open discussion follows review/rebuttal/re-review/gate. Deep exploration follows gap/candidate/review/revision/proposal decisions; Reader tasks are dispatched by the parent. Registration retries reuse delivery identity, and completion does not approve a research claim. No hooks are required.
- When cancelling, use native cancellation and record its observed outcome. Neither a prepared assignment nor elapsed time proves execution or termination.

## Hermes and Pi

Codex and Pi use ka_delphi through the shared MCP server and the native agent capability available in that installation. Hermes can connect the same server or retain its existing registration, delegate_task, skill reader and explicit optional tool mode. The absolute common CLI remains a fallback for every host. This contract does not install a separate agent harness or emulate a missing host agent tool. Installed-host execution is verified separately.
