---
name: ponder-forge-usage
description: Operate Ponder-Forge complex-problem team workflows from Hermes.
version: 0.1.0
author: Hermes Agent
---

# Ponder-Forge Usage

Use Ponder-Forge for complex problems that need multiple child agents, structured evidence, independent review, and graph-backed finalization.

Core operating contract:

1. Start with `ponder_forge_start`.
2. Call `ponder_forge_plan` before delegation.
3. Call `ponder_forge_prepare_delegations`, then call native `delegate_task` with the returned payload.
4. Ensure child agents call `ponder_forge_report_submit`.
5. Use profile-specific evidence: research, coding, design, analysis, or math.
6. Use independent reviewer tasks for critical verdicts.
7. Call `ponder_forge_gate_status` and `ponder_forge_finalize` before final answer.
8. If finalization blocks, continue with the returned follow-up tasks.

Ponder-Forge does not modify Hermes core and does not override `delegate_task`.
