# Long runs and recovery

The wrapper is a detached process launched with the plugin's absolute script and interpreter. It executes one authorized RunSpec, limits saved stdout/stderr bytes, enforces timeout and writes terminal evidence. Closing the MCP connection does not cancel a run.

`ka_research_status` reads saved state. It never calls a collector or writes a heartbeat. A missing worker for an unfinished record is reported as interrupted without changing the record. Stop verifies recorded process identity before signalling; repeated stops preserve an existing terminal result.

Use native Codex planning and ordinary project notes for research decisions and handoffs. Run and report paths are durable recovery anchors. There is no plugin goal loop, stage controller or mandatory checkpoint API. A same-key retry returns the original request instead of repeating uncertain side effects.

If derived recording is partial, the run record remains authoritative. Explicit maintenance can reconcile it after execution ends; it cannot invent missing metrics or turn an interrupted execution into success. See the human [maintenance guide](ADMIN_CLI.md) when this operation is actually needed.
