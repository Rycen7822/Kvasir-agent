# Active state

- Goal: Complete the Kvasir-agent short-name migration to `ka_*`.
- Current state: all 69 schema names use `ka_*`; MCP and CLI entrypoints expose only `ka_*` tools. Renamed scripts, environment keys, runtime `.ka/` paths, markers, docs, and tests. Full suite: 408 passed; all 782 original tracked paths are present under their new names.
- Reusable anchors (max 15):
  - `kvasir_agent/runtime/schemas.py:300-410` — schema names, aliases, and public tool list.
  - `scripts/ka_mcp.py:1-49` — MCP stdio and smoke entrypoint.
  - `kvasir_agent/mcp/surface_allowlist.py:1-65` — CLI name boundary and allowlist.
  - `kvasir_agent/runtime/vendor/kvasiragent/tinytex.py:118-139` — missing runtime guidance.
  - `tests/test_no_cli_prompt_surface.py:98-122` — CLI filter term assertion.
  - `kvasir_agent/runtime/vendor/kvasiragent/config/service.py:575-588` — provider launch instructions.
  - `kvasir_agent/runtime/vendor/kvasiragent/config/service.py:1346-1360` — Codex binary hint.
  - `kvasir_agent/runtime/vendor/kvasiragent/config/service.py:1408-1420` — provider environment hint.
  - `kvasir_agent/runtime/vendor/kvasiragent/config/service.py:1447-1500` — probe failure guidance.
  - `scripts/ka_native_cli.py:105-145` — public schemas and alias lookup.
  - `scripts/ka_native_cli.py:140-228` — alias handling in CLI call and schema paths.
  - `tests/test_upgrade6_admin_legacy_sunset.py:1-45` — disabled alias contract.
  - `README.md:18-30` — merged opening description uses Kvasir-agent and `ka_*`.
  - `README.md:139-152` — merged operation boundary uses `ka_bash_exec`.
  - `tests/test_codex_adapter_contract.py:190-207` — README naming assertions.
