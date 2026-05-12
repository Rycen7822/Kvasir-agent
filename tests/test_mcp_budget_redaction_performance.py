from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

from codex_scientist.adapters.cli import normalize_envelope
from codex_scientist.mcp.tool_registry import call_tool, list_tool_specs


def test_mcp_tool_descriptions_and_outputs_are_bounded(tmp_path: Path):
    specs = list_tool_specs()
    assert specs
    assert all(len(spec.description) <= 160 for spec in specs)

    context = call_tool("cs_context_pack", {"project": str(tmp_path), "max_chars": 240})
    assert context["ok"] is True
    assert context["chars"] <= 240
    assert len(context["content"]) <= 240

    search = call_tool(
        "cs_skill_search",
        {
            "raw_user_request": "请检查 manifest 和 queue 状态",
            "description_query": "manifest queue status",
            "workflow_query": "validate manifest queue status context",
            "limit": 5,
            "max_chars": 900,
        },
    )
    assert search["ok"] is True
    assert search["tokens_estimate"] <= 900
    assert all("content" not in item for item in search["candidates"])


def test_mcp_normalized_payload_redacts_secret_like_values():
    private_key = "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nabc123\n-----END OPENSSH PRIVATE KEY-----"
    github_token = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz"
    openai_token = "".join(["sk", "-proj-", "abcdefghijklmnopqrstuvwxyz1234567890"])
    aws_key = "AKIA" + "1234567890ABCDEF"
    payload = normalize_envelope(
        {
            "ok": True,
            "api_key": "sk-sho...leak",
            "message": "authorization: Bearer *** token=my-token password=hunter2 AWS_SECRET_ACCESS_KEY=aws-secret client_secret=oauth-secret AccountKey=storage-secret",
            "url": "https://user:***@example.com/path",
            "private_key": private_key,
            "github_token": github_token,
            "openai_token": openai_token,
            "aws_key": aws_key,
            "connection": "postgresql://user:secretpass@localhost:5432/db",
        }
    )

    rendered = str(payload)
    assert "sk-sho...leak" not in rendered
    assert "my-token" not in rendered
    assert "hunter2" not in rendered
    assert "aws-secret" not in rendered
    assert "oauth-secret" not in rendered
    assert "storage-secret" not in rendered
    assert "secretpass" not in rendered
    assert "abc123" not in rendered
    assert github_token not in rendered
    assert openai_token not in rendered
    assert aws_key not in rendered
    assert "[REDACTED]" in rendered


def test_mcp_readonly_calls_are_fast_enough_for_context_budget():
    start = perf_counter()
    listed = [spec.as_dict() for spec in list_tool_specs()]
    search = call_tool(
        "cs_skill_search",
        {
            "raw_user_request": "use CodexScientist MCP status",
            "description_query": "mcp status skill retrieval",
            "workflow_query": "doctor status skill load",
            "limit": 5,
        },
    )
    elapsed = perf_counter() - start

    assert listed
    assert search["ok"] is True
    assert elapsed < 2.0


def test_mcp_readonly_calls_are_safe_under_basic_concurrency(tmp_path: Path):
    def call_once(index: int) -> bool:
        payload = call_tool("cs_queue_status", {"project": str(tmp_path), "limit": 20})
        return payload["ok"] is True and payload["mcp"] is True

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(call_once, range(12)))

    assert all(results)
