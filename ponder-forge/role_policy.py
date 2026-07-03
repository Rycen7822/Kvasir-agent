from __future__ import annotations

MUTATING_TOOLS = {
    "write_file",
    "patch",
    "skill_manage",
    "memory",
    "hy_memory_add",
    "hy_memory_update",
    "hy_memory_delete",
}
BLOCKED_FOR_ALL_CHILDREN = {
    "ponder_forge_finalize",
    "send_message",
    "cronjob",
}


def _is_reviewer(role: str) -> bool:
    return "reviewer" in role or "review" in role or "critic" in role


def evaluate_role_policy(role: str, tool_name: str) -> dict | None:
    if tool_name == "ponder_forge_report_submit":
        return None
    if tool_name in BLOCKED_FOR_ALL_CHILDREN:
        return _block(role)
    if _is_reviewer(role) and (tool_name in MUTATING_TOOLS or tool_name == "terminal"):
        return _block(role)
    if role.startswith("research") and tool_name in MUTATING_TOOLS:
        return _block(role)
    if role.startswith("math") and tool_name in MUTATING_TOOLS | {"terminal"}:
        return _block(role)
    return None


def _block(role: str) -> dict:
    return {
        "action": "block",
        "message": f"Ponder-Forge policy: this {role} role cannot mutate files or finalize. Submit evidence with ponder_forge_report_submit.",
    }
