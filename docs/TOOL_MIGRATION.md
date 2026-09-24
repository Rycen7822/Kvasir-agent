# Migration from the earlier 24-tool interface

| Earlier responsibility | Current owner |
| --- | --- |
| Project/resume/checkpoint/context packing | `ka_research_status` plus native file reads and handoff notes |
| Requirements, memory, literature, outlines, analysis documents | Native Codex file/research tools |
| Environment registration and formal command bookkeeping | RunSpec/environment snapshot validated by `ka_experiment_run` |
| Trajectory, method results and experiment registration | Automatic per-run result and terminal event |
| Claim/material checks | `ka_evidence_check` over actual run evidence |
| External results | `ka_evidence_import`, always preserving unverified origin |
| Stop/cancel | `ka_experiment_stop` |
| Profiles, hidden executor aliases and generic CLI handler calls | Removed from public execution |
| Project creation and old state migration | Explicit human maintenance; see [ADMIN_CLI.md](ADMIN_CLI.md) |

There are exactly five MCP tools and one registered research skill. Old names fail closed, including schema lookup aliases. State v3 uses stable identity and explicit migration. Existing v2/quest data is never implicitly converted on a read or first business write. Scientific judgment, novelty analysis and prose review belong to Codex; previous file-presence heuristics are not a scientific approval gate.

General memory cleanup also removes the internal `ka_memory_search/read/list_recent/write` implementations and `ContextPackService`. There is no replacement memory switch or automatic memory injection. Archived playbooks may describe those retired interfaces; use the current research tools and native document reads instead. Research Wiki, paper/idea documents, trajectory retrieval and negative experiment records are retained, as are all five current tools. Existing files are not erased or automatically migrated.
