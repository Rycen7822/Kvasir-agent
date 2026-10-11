---
name: delphi-idea-spark
description: Discuss research ideas or deeply develop a research proposal through Delphi's shared ledger and native agents.
---

# Idea-Spark

Use `ka_delphi` with `workflow=idea_spark` and the absolute research project directory. Open with `action=open`, the user's `goal` and a fresh `request_id`. Select `mode=open_discussion` for an existing idea (default), or `deep_exploration` for IdeaScientist-style proposal development. Reuse the request ID only when retrying the same allocation.

Read the returned `instruction_path` in full once. Edit the supplied input templates and follow `next_call`: prepare → native launch/wait → collect → update → finish. Resume through `action=status` with the existing room_id. Load only selected mode/role instructions; registration is delivery, and the parent decides scientific conclusions and checkpoints.

Pass each worker the complete returned instructions, input files and output/scratch paths. Workers write a complete Markdown file and return its absolute path; if writing fails, preserve the full reply at that path. After actual native completion, the parent collects receipt_paths and reads complete files. Use actual host signatures and the user's model restrictions; the MCP does not launch, wait or cancel agents. No hooks are required.

If ka_delphi is unavailable, use the explicit CLI fallback in the [native host contract](../../delphi/HOSTS.md). Configuration, manual initialization and dashboard administration stay in CLI.
