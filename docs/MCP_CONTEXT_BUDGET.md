# Context budget

The baseline advertised 24 tools / 42 operations and measured 6,408 tokens for compact host definitions. The new surface has five tools with file paths instead of embedded specification objects. The measured v0.2 candidate uses 698 o200k_base tokens for source definitions and 778 for full host definitions, a reduction of 87.86%. This is below the 1,500-token limit; it does not imply every host injects or bills that entire definition array on every turn.

One research skill is discovered. Its detailed file contracts are read only when preparing the corresponding operation. Six former stage skills are historical references outside the discovery root. Project creation has no MCP schema or automatically discovered skill metadata; its independent manual is packaged outside `skills/`.

Typical receipts target 100–200 tokens, status summaries 300–800, and errors under 1,000. Runtime uses fixed field/entry limits and bounded strings rather than a model tokenizer dependency. A status summary includes at most five runs; full records and reports stay on disk. MCP structured/text compatibility representations share the same short receipt; there is no extra top-level business copy.

The thin schema is not the total workflow cost: first use may require reading an environment/RunSpec example or schema. Measurements must separately report tool definitions, actual text receipts, active skill metadata/body and on-demand contract cost. Tool-search or deferred loading is not assumed to eliminate all metadata without real host evidence.

## Measured candidate

Using compact JSON for definitions and actual `content.text` for receipts: installed calls used 23–125 tokens, a synthetic 100-record status returned 414 tokens, and a long Chinese invalid specification produced a 28-token error. The single skill file is 583 tokens when explicitly loaded.

First use still has a cost: the file-contract guide is 790 tokens, the environment and run examples are 166 and 111 tokens, and their complete schemas are 754 and 607 tokens. Load the relevant example or schema as needed. These costs are separate from the advertised tool definitions.

Verification used an isolated Codex installation and a real ordinary-session initial provider request captured at a loopback fixed-response endpoint. The research plugin was present; the manual initialization name, description, path, body and CLI instructions were absent. No paid model call was made. This establishes the tested startup behavior, not a guarantee about user-explicit future file reads.
