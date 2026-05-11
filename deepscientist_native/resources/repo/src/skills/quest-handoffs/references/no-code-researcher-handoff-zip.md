# No-code researcher handoff zip for research/DeepScientist quests

Use when the user wants to send a compact package to another researcher for analysis, without code or rerun infrastructure.

## Package shape

Create the zip under the current quest root, for example:

- `exports/quest001_researcher_handoff_<YYYYMMDD_HHMMSS>.zip`

Include a root-level `README_FOR_RESEARCHER.md` inside the package. It should tell the recipient:

1. the source quest root and package creation time;
2. the intended use: independent reading / sanity checking / result analysis, not rerunning code;
3. the recommended reading order;
4. one-paragraph project/result summary;
5. conservative claim boundaries;
6. what is included and intentionally omitted;
7. where the manifest files live;
8. suggested reviewer questions.

Also include:

- `PACKAGE_MANIFEST.md` with human-readable path / size / SHA256 rows;
- `PACKAGE_MANIFEST.json` with machine-readable metadata;
- `FILE_TREE.txt` with the compact zip file list.

## Typical inclusions

Prefer source-of-truth documents and small result artifacts. Start compact; expand only when the user asks for more audit material. A broad package can be useful for internal handoff, but for an external researcher analysis zip the default should be the smallest set that supports reading the idea, protocol, result report, and final evidence.

Minimal external-review set:

- root package guide/manifests: `README_FOR_RESEARCHER.md`, `PACKAGE_MANIFEST.md`, `PACKAGE_MANIFEST.json`, `FILE_TREE.txt`;
- current entry/status: `experiments/CURRENT_STATUS.md`;
- concise result report: `experiments/MAIN_EXPERIMENT_RESULTS_REPORT.md`;
- the 2-3 active idea/protocol/spec docs needed to understand the claim, not the whole `idea/` directory;
- final main experiment `RESULT.json` and, if concise enough, `RUN.md`;
- source verification JSON and the formal target records needed for the central claim;
- one traceability bundle such as post-hoc G2 analysis when the report depends on it;
- compact generated result surfaces: catalog plus selected table markdown files and, if useful, one contact-sheet figure instead of every figure PNG/PDF.

Broader internal-review additions, only when requested:

- root overview docs: `brief.md`, `plan.md`, `status.md`, `SUMMARY.md`, `AGENTS.md`;
- active idea docs under `idea/` but not `idea/backup/`, `idea/archive/`, or routine audits unless explicitly requested;
- experiment plan / command docs such as `experiments/EXPERIMENT_EXECUTION_PLAN.md` and `experiments/正式实验命令.md`;
- resource/reference summaries and bibliography indexes, but not raw PDFs or model/data caches;
- relevant manifests for resources, splits, floorplans, selector subsets, and streaming corpus;
- all generated paper-facing figures/tables/catalogs;
- train/eval logs, orchestrator/cursor/consumption records needed for deep audit;
- supporting benchmark/statistics evidence needed for claims in the report;
- selected DeepScientist artifact records for provenance.

## No-code / no-heavy-artifact policy

Omit by default:

- source code directories: `experiments/src/`, `experiments/scripts/`, `scripts/`, `resources/code/`;
- source/code extensions: `.py`, `.sh`, `.ipynb`, `.js`, `.ts`, `.c`, `.cpp`, `.h`, `.rs`, `.go`, etc.;
- model weights/checkpoints: `.pt`, `.pth`, `.bin`, `.safetensors`;
- large arrays/intermediates: `.npz`, `.npy`, `.pkl`, `.pickle`;
- raw model/dataset caches and downloaded third-party code repos;
- reference PDFs unless the user explicitly asks for PDFs;
- `.ds/` runtime logs and the full `.git/` repository;
- secondary workspace copies if the current user instruction says not to sync/touch them.

Represent omitted checkpoint/model provenance through small JSON files such as `checkpoint_manifest.json`, `systems_metrics.json`, and recorded SHA256 fields.

## Verification checklist

After creating the package:

1. run `zipfile.ZipFile(...).testzip()` or equivalent; expected result: `null` / no bad file;
2. scan zip entry names for forbidden extensions and forbidden path fragments;
3. verify required core files are present for the selected package tier:
   - minimal tier: root README/manifests, current status, main report, key idea/protocol/spec docs, final `RESULT.json`, source verification JSON, formal target records, traceability JSON, and compact figure/table catalog/surfaces;
   - broad tier: include the above plus any requested command docs, manifests, logs, and provenance records;
4. compute zip size and SHA256;
5. if the package directory was staged separately before zipping, remove the unpacked staging directory and keep only the zip unless the user asked for both;
6. if the new minimal package supersedes a prior broad package in the same `exports/` directory, remove or clearly rename/archive the broad zip so the recipient is not sent the wrong file;
7. keep exports out of git tracking (for example with local `.git/info/exclude`) unless the user explicitly asks to version the zip;
8. record a milestone artifact with zip path, size, SHA256, file count, omissions, selected tier, and verification results.

## DeepScientist artifact note

For document/package maintenance, prefer recording a `milestone` rather than a generic `report`. In one Quest 001 session, `ds_artifact_record(kind="report")` semantically matched an old report artifact and did not create a clear new record, while `kind="milestone"` produced the intended durable checkpoint.
