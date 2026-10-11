# Context budget

Current source keeps three tools with file paths instead of embedded specifications: **519 o200k_base tokens / 2,247 UTF-8 bytes**. The preceding five-tool source catalog measured 698 tokens / 3,117 bytes in the same compact JSON format; merging experiment and evidence actions reduces catalog tokens by 25.6%. The earlier published v0.3.0 native Codex catalog measured 698 tokens / 3,118 bytes. Current schemas and examples contain no checksum fields.

These are tokenizer estimates for the measured text, not exact model context or billing. Host wrappers, server names, caching and deferred discovery can change what is sent. The historical 24-tool surface measured 6,408 tokens; that earlier host-wrapper measurement is not identical to the current native catalog measurement.

## Current source estimates

| Material | Estimated tokens | UTF-8 bytes |
| --- | ---: | ---: |
| Three compact tool definitions | 519 | 2,247 |
| Active skill name and description, compact metadata | 25 | 118 |
| Active skill file, when explicitly read | 682 | 3,487 |

## Earlier host measurements (published v0.3.0)

These measurements predate hash simplification. They are retained as host integration evidence, not a fresh installation or provider-request measurement of the modified source.

| Material | Estimated tokens | UTF-8 bytes |
| --- | ---: | ---: |
| Native Pi rendered MCP namespace section, codemode | 46 | 197 |
| Native Pi rendered skill metadata block, optional skill | 144 | 640 |
| Empty initialized project status, native Codex call | 153 | 509 |
| Default status over 100 synthetic records | 521 | 1,643 |
| Large invalid specification error | 22 | 79 |

Earlier Pi 1.0.0 native SDK discovery confirmed that `codemode` registered five callable tools and declared zero Kvasir tool schemas directly; `direct` declared five. Those host measurements describe the preceding five-tool configuration, not a fresh native-host measurement of the current three-tool interface. The namespace and skill blocks above use Pi's native rendering functions for that verified configuration; they are not a captured provider request or the whole host prompt. Optional loading of the research skill has a separate metadata cost.

Status returns at most five recent runs, ordered by actual creation time, and counts omitted records. Default summaries omit detailed observations; one-run status exposes bounded progress/cost details. Errors have bounded strings. Full records, index entries and reports remain on disk. Text and structured MCP compatibility representations contain the same short receipt.

## On-demand cost

| File | Estimated tokens |
| --- | ---: |
| Run v2 example | 187 |
| Complete run schema, v1 and v2 | 1,623 |
| Comparison example / schema | 332 / 1,486 |
| Candidate record schema | 871 |
| Complete six-kind research schema | 4,838 |

Use the relevant example and the individual record schema linked from [RESEARCH_RECORDS.md](RESEARCH_RECORDS.md). The complete research union is the validation/publication authority; it need not be read for one record kind. Detailed contracts and seven workflow templates are outside automatic skill metadata and MCP definitions.

Project creation has no MCP tool or registered skill metadata. Its independent manual is outside `skills/`. Source/packaging gates verify this boundary; Pi native skill discovery found one active research skill and no manual. Codex 0.160.0 native app-server discovery/call and Pi native MCP pipeline calls were verified without model requests. Pi calls used a labeled synthetic assistant fixture required by the host pipeline. Earlier v0.2 startup capture remains historical evidence, not a new v0.3 provider-request test.
