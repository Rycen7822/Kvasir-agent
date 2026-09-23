# Hidden Admin/Debug CLI

This document is not part of the default agent research path. It is the only document that should expose the hidden admin/debug CLI command examples.

Kvasir-agent keeps `scripts/kactl.py` for human administration, debugging, CI, migration, and recovery. The default Codex research workflow must use MCP `ka_*` tools and fail closed when MCP is unavailable.

Use these commands only when a human/admin/debug/CI/recovery task explicitly needs CLI output:

```bash
python scripts/kactl.py doctor --format json
python scripts/kactl.py list-tools --format json
python scripts/kactl.py manifest validate --format json
python scripts/kactl.py queue status --format json
```

Rules:

- Do not place these commands in plugin default prompts or runtime skill views.
- Do not use the CLI as an automatic recovery path for missing MCP tools.
- Keep CLI compatibility tests, but keep the agent-facing research surface MCP-only by default.
