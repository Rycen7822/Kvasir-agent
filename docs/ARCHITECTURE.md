# Architecture

```text
5 MCP tools -> EvidenceService -> ResearchState v3
                      |                 |
                      |                 +-- research.yaml / events
                      +-- per-run wrapper -> run.json / logs / result.json
                      +-- checks and copied external evidence
manual maintenance CLI -> explicit state creation / migration / repair
```

`services/evidence_contracts.py` owns strict file contracts. `research_state.py` owns explicit paths, stable project identity, atomic records and a project write lock. `evidence.py` combines guards and operations. `evidence_runner.py` executes one run and finalizes evidence without requiring status polling. It has the lifetime of that run, not a permanent daemon.

The new default chain never calls the legacy global runtime, vendor home setup, quest shims or environment-based project routing. Old runtime modules with offline consumers remain internal. Old generic CLI scripts reject operations. MCP profile/filter machinery and orphan routing modules are removed.

General memory cards, their legacy read/write tools, automatic card injection and session context packs are removed from the implementation. Research documents, paper/idea records, trajectory search and experiment failure history remain. Existing `memory/ideas`, `memory/papers` and historical document paths stay readable; cleanup never deletes project data. Shared Markdown parsing lives independently of memory services.

The state root is `<project>/Kvasir-agent/`. At creation it contains only `research.yaml` and `events/{events.jsonl,write.lock}`. Environment snapshots, `runs/<id>/`, `artifacts/checks/`, `artifacts/imports/` and explicit migration records appear only when needed. Reading state never migrates, repairs, collects or normalizes it on disk.

A run record is authoritative. Its `result.json` and terminal event are idempotent derived data; failure leaves `derivation_status=partial` for explicit reconciliation. Every run freezes the request and environment. Claims resolve those records and recorded seeds. Imported bytes and older evidence never acquire managed execution trust automatically.

Migrations archive original bytes, map run IDs and known path fields, and commit the v3 manifest last. A pending marker blocks ordinary operations until explicit resume. This is a recoverable multi-file transaction, not a claim that one atomic manifest rename makes every file update atomic.
