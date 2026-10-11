---
name: delphi-ponder-forge
description: Solve complex problems with FrontierAgent high/max strategies and native agents.
---

# Ponder-Forge

Use `ka_delphi` with `workflow=ponder_forge` and the absolute research project directory. Open with `action=open`, the user's `goal`, a fresh `request_id` and `effort=max` (default) or high. Read the returned instruction_path in full once; it contains the complete FrontierAgent strategy with native-host operation mappings.

Edit supplied templates and follow next_call: plan → prepare → native launch → record → native wait → collect. Pass complete returned instructions and file paths to each worker; collect full files using receipt_paths. Reuse native agents for serial follow-ups by logical role name. Use a new request_id for each new assignment or verifier; retry the same allocation with its original ID.

Query bounded status with the existing run_id. Prepare independent final/local checks through verify, execute them with native agents and interpret their reports. The parent resolves/cancels board questions and saves the complete final draft through finish; partial completion requires an observed reason. Delivery does not resolve scientific questions. Follow actual host signatures and user model restrictions; the MCP owns state, the host owns agent lifetimes.

If ka_delphi is unavailable, use the explicit CLI fallback in the [native host contract](../../delphi/HOSTS.md). Maintenance and dashboard administration remain in CLI.
