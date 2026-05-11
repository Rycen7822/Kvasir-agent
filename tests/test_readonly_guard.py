from __future__ import annotations


def test_readonly_guard_allows_editable_changes_and_blocks_readonly_eval_changes():
    from codex_scientist.services.readonly_guard import check_readonly_changes

    allowed = check_readonly_changes(
        changed_paths=["src/model.py"],
        editable_paths=["src/**"],
        readonly_paths=["data/**", "eval/**"],
        eval_paths=["eval/**"],
    )
    assert allowed == {"ok": True, "blocked_paths": []}

    blocked = check_readonly_changes(
        changed_paths=["src/model.py", "eval/evaluate.py", "data/test.jsonl"],
        editable_paths=["src/**"],
        readonly_paths=["data/**"],
        eval_paths=["eval/**"],
    )
    assert blocked["ok"] is False
    assert blocked["error_type"] == "failed_readonly"
    assert blocked["blocked_paths"] == ["eval/evaluate.py", "data/test.jsonl"]
