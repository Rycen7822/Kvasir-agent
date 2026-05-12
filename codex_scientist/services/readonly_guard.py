from __future__ import annotations

from fnmatch import fnmatch


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def check_readonly_changes(
    *,
    changed_paths: list[str],
    editable_paths: list[str],
    readonly_paths: list[str],
    eval_paths: list[str],
) -> dict:
    blocked: list[str] = []
    for path in changed_paths:
        is_editable = _matches_any(path, editable_paths)
        is_guarded = _matches_any(path, readonly_paths) or _matches_any(path, eval_paths)
        if not is_editable and not is_guarded:
            continue
        if is_guarded:
            blocked.append(path)
    if blocked:
        return {"ok": False, "error": "Readonly or eval paths changed", "error_type": "failed_readonly", "recoverable": False, "blocked_paths": blocked}
    return {"ok": True, "blocked_paths": []}
