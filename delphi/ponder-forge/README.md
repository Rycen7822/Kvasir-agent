# Ponder-Forge

FrontierAgent Apodex 1.1 **high/max** strategies for a host's native agent team. Default: max. This plugin supplies strategy and research state; the host runs models.

Codex discovers the root Ponder skill and uses the [Delphi CLI and host contract](../HOSTS.md). Pass an explicit project state directory to the common CLI; direct Hermes component commands keep their original defaults when `DELPHI_HOME` is unset.

## Start

```sh
python3 /path/to/ponder-forge/cli.py start --goal "Your complex question"
python3 /path/to/ponder-forge/cli.py start --goal "Your complex question" --team-effort high
python3 /path/to/ponder-forge/cli.py plan --run-id RUN_ID
```

Read the returned full coordinator prompt. Create a task board and explicit assignments, execute them using native host tools, retain full reports, arbitrate conflicts, verify the complete draft, and save the final answer. See [the usage skill](resources/skills/ponder-forge-usage/SKILL.md) for JSON examples.

The task board tracks research resolution separately from assignment execution. Normal completion requires all board questions resolved/cancelled; interrupted work can save an explicit partial result. The CLI does not certify claims or run its own agent harness. Existing database/history stays in place.

## Source and adaptation

Core templates and `render_team_effort` in frontier_prompts.py come unchanged from [ApodexAI/FrontierAgent](https://github.com/ApodexAI/FrontierAgent), commit `179709fee18ae8506ac77bc724b3cea0ac1e0dbf`, workflows/agent_team/prompts.py. These portions retain [Apache-2.0](licenses/FrontierAgent-APACHE-2.0.txt). Local strategy.py adapts tool entry points, task completion to native final replies, and supplied filesystem paths, and makes asynchronous execution conditional on the native host supporting it. It corrects the source prose's `blocked` state to `cancelled`, matching the source's actual four-state task board. No upstream AgentOS, model runtime or asynchronous bus is copied. The host's capabilities and limits determine how assignments execute.

`high` retains the complete base workflow including final verification. `max` retains the exact additional five-step policy; the final team_effort tag is last. Workers receive only their relevant research/local verifier/final verifier role. Profiles remain optional domain hints; no fixed eight-route expansion is created.

## Verification

```sh
pytest -q tests
python3 scripts/run_mini_benchmark.py --output /tmp/ponder-offline/summary.json
python3 scripts/copy_install_smoke.py --target /tmp/ponder-copy/ponder_forge
```

The mini script exercises offline fixtures and CLI state transitions, not model research quality. Copy installation verifies packaging and registration; real native agent execution requires a separate live run.
