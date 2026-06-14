# Idea-Spark full-function test problems

Test date: 2026-06-14
Plugin under test: `/home/xu/.hermes/plugins/idea_spark -> /home/xu/project/autosci-delphi/idea-spark/idea_spark`
Hermes profile: default, `HERMES_HOME=/home/xu/.hermes`
Primary test DB: `/tmp/idea_spark_full_function_20260614_191414.sqlite3`
Primary room: `full-fn-20260614_191414`
Machine summary: `/tmp/idea_spark_full_function_summary_20260614_191414.json`
Payload directory: `/tmp/idea_spark_full_function_payloads_20260614_191414`

## Final verdict

The new Idea-Spark plugin passed real end-to-end testing for default CLI-first mode, explicit tool-mode registration, canonical ledger operations, dashboard read paths, Markdown export, regression tests, and a realistic old-flow `delegate_task` room discussion through a shared Idea-Spark ledger.

Unresolved product / workflow issue count: 4

Fixed during follow-up: P008, P011. Closed / not-product-defect records from live testing: P001-P006. They are retained below because they were recorded immediately during the run, then resolved by targeted retest, source inspection, or a follow-up patch.

| ID | Status | Severity | Area | Summary |
|---|---|---:|---|---|
| P007 | Open | Important | `idea_spark_room_status` | `counts.open_needs` is a total row count, not an unresolved/open need count, while the name implies unresolved/open needs. |
| P008 | Fixed in workspace | Important | delegated child prompt / bundled skill | CLI-first children were given `skills` and did load the skill, but parent prompt did not pass `PAYLOAD_DIR` and the skill checklist did not hard-require a scratch payload directory, so temporary JSON payloads were written to repo root. |
| P009 | Open | Minor | `idea_spark_round_wait` payload ergonomics | Parent-style wait payload without `phase` fails; examples/help should make `phase` unavoidable or support round-only waits. |
| P010 | Open | Important | `idea_spark_round_wait` barrier semantics | Multi-role R1 used role-specific phases; `round_wait` with a shared phase reported no arrivals even though both agents had posted. |
| P011 | Fixed in workspace | Important | room creation UX / bundled skill | Creating a room did not force the parent to immediately give the user a concrete dashboard room link. |
| P012 | Open | Important | dashboard link availability | A returned room link can be impossible to open when the dashboard server is not actually running on that host/port. |

## Test coverage summary

### Install / plugin surface

- `hermes plugins list --plain --no-bundled` shows `idea-spark` enabled as a user plugin.
- Installed plugin entry is a symlink to the current source tree.
- `hermes idea-spark --help` works from the default profile.
- `hermes idea-spark config show` works and reports `tools.enabled=false` after restore.
- Fresh default registration from installed plugin reports exactly:
  - tools: `[]`
  - skills: `['idea-spark-usage']`
  - CLI: `['idea-spark']`
- Explicit tool-mode toggle through real CLI works:
  - `hermes idea-spark config set-tools true`
  - fresh registration reports 14 `idea_spark_*` tools
  - config was restored to `tools.enabled=false` after the test

### CLI operation lifecycle

Real commands used `hermes idea-spark call <operation> --json-file ...` or `--stdin` against an isolated SQLite DB.

Passed canonical operations:

- `idea_spark_room_create`
- `idea_spark_room_join`
- `idea_spark_room_status`
- `idea_spark_message_post`
- `idea_spark_message_read`
- `idea_spark_round_wait` complete path
- `idea_spark_round_wait` timeout path
- `idea_spark_artifact_create`
- `idea_spark_artifact_read`
- `idea_spark_artifact_link` with valid relation `critiques`
- `idea_spark_artifact_status_update`
- `idea_spark_gate_record` with `close_room=true`
- `idea_spark_need_create`
- `idea_spark_need_update` to `resolved`
- `idea_spark_room_export` with `format=markdown`

Passed CLI edge/error paths:

- `--stdin` payload path
- unknown operation exits non-zero and returns structured JSON
- invalid JSON exits non-zero and returns structured JSON
- unsupported export format exits non-zero and returns structured JSON

### Dashboard read paths

Dashboard was launched against the isolated test DB.

Passed endpoints:

- `/` index page
- `/room/<room_id>` static room shell
- `/api/rooms`
- `/api/rooms/<room_id>/snapshot`
- `/api/rooms/<room_id>/events?once=1`

### Realistic delegated-room scenario

The old-flow style scenario used one parent-created room plus four `delegate_task` children using the installed CLI only:

- `PriorArtBreaker`: joined, read seeds, wrote `PriorArtEvidence` and `NoveltyObjection`, linked artifacts, posted message.
- `ExperimentPlanner`: joined, read seeds/messages, wrote `ExperimentPlan` and `BenchmarkRequirement`, linked artifacts, posted message.
- `AuthorAdvocate`: joined after R1, read prior artifacts/messages, wrote `Rebuttal`, `RevisionPlan`, and an `OpenNeed`, linked artifacts, posted message.
- `Gatekeeper`: joined after R2, read full ledger, wrote `ScoreCard` and `MetaReview`, linked artifacts, posted message, and recorded a terminal `novelty_gate` with `close_room=true`.

Final delegated-room state:

```text
room_id: delegated-flow-20260614_192310
status: gated
has_terminal_gate: true
decision: needs_more_evidence
participants: 4
messages: 4
artifacts: 12
gates: 1
open_needs: 1
```

Final export and dashboard checks passed:

- Markdown export contained `PriorArtBreaker`, `AuthorAdvocate`, `Gatekeeper`, `needs_more_evidence`, `artifact_91e258b23ef4`, and `artifact_066d28aeac68`.
- Dashboard `/api/rooms/delegated-flow-20260614_192310/snapshot` contained `gate_ea12c3a77568`, `needs_more_evidence`, and `gatekeeper`.
- Dashboard `/api/rooms/delegated-flow-20260614_192310/events?once=1` emitted the final snapshot.

### Regression tests

- Full project suite from the first full-function run: `88 passed in 3.55s`
- Targeted post-retest suite: `53 passed in 3.09s`
- Final post-delegated-scenario full suite: `88 passed in 3.51s`
- Post-room-link follow-up full suite: `91 passed in 3.57s`
- Real CLI room-create smoke with `dashboard_base_url=http://127.0.0.1:8899` returned `room_url=http://127.0.0.1:8899/room/link-smoke-room`

## Open issues

### P007 — Important — `idea_spark_room_status` need count semantics

Status: Open

#### Summary

After the only need in the test room was updated to `resolved`, `idea_spark_room_status` still returned:

```json
"counts": {
  "open_needs": 1
},
"open_need_summary": {
  "open": 0,
  "claimed": 0,
  "resolved": 1,
  "stale": 0,
  "cancelled": 0
}
```

The data itself is not lost: `open_need_summary` correctly shows the need as resolved. The problem is that `counts.open_needs` is named like an unresolved/open count but currently counts all rows in the `open_needs` table.

#### Evidence

```text
Command:
IDEA_SPARK_DB=/tmp/idea_spark_full_function_20260614_191414.sqlite3 \
HERMES_HOME=/home/xu/.hermes \
hermes idea-spark call idea_spark_room_status --stdin

Payload:
{"room_id":"full-fn-20260614_191414"}

Observed:
"counts": {"artifacts": 6, "gates": 1, "messages": 2, "open_needs": 1, "participants": 2}
"open_need_summary": {"cancelled": 0, "claimed": 0, "open": 0, "resolved": 1, "stale": 0}
```

SQLite confirmation:

```text
open_needs rows: 1
need statuses: [{'status': 'resolved', 'n': 1}]
```

Source confirmation:

```python
def _room_counts(conn, room_id):
    counts = {}
    for name in ["participants", "messages", "artifacts", "gates", "open_needs"]:
        counts[name] = conn.execute(
            f"select count(*) as n from {name} where room_id = ?", (room_id,)
        ).fetchone()["n"]
    return counts
```

#### Impact

A parent/orchestrator that reads only `counts.open_needs` may think unresolved evidence gaps remain even when all needs were resolved. This can make gate/closeout logic overly conservative or confusing.

#### Recommended fix

Low-risk compatible fix:

1. Add `counts.total_needs` for all rows in the `open_needs` table.
2. Change `counts.open_needs` to count only unresolved statuses: `open` and `claimed`.
3. Keep `open_need_summary` unchanged.
4. Add a regression test: create need -> update to `resolved` -> assert `counts.open_needs == 0`, `counts.total_needs == 1`, and `open_need_summary.resolved == 1`.

Alternative compatibility-preserving fix if existing consumers depend on current semantics:

- Keep `counts.open_needs` as-is but add `counts.unresolved_needs`, and document that `counts.open_needs` is a legacy table-row count. This avoids breaking consumers but leaves the misleading field name in place.

## Closed / retested records from live log

### P001 — Closed as invalid test payload — `idea_spark_artifact_link`

Initial live-log record:

```text
rc=1 stdout={"error": "invalid relation", "relation": "challenges", "success": false} stderr=
```

Resolution:

`challenges` is not an allowed relation. The allowed set includes `supports`, `contradicts`, `critiques`, `rebuts`, `supersedes`, `evolves_from`, `requires`, `assumes`, `cites`, `compares_against`, `fails_under`, `passes_gate`, `rejected_by_gate`, `introduced_by_transition`, `transported_from_prior_schema`, and `decomposes`.

Targeted retest with valid relation `critiques` passed:

```text
rc=0
stdout={"link_id": 1, "room_id": "full-fn-20260614_191414", "success": true}
```

No product defect confirmed.

### P002 — Closed as invalid expected heading — Markdown export title

Initial live-log record expected `# Idea-Spark Room Export`.

Resolution:

The implemented and documented renderer uses:

```text
# Idea-Spark Room Report
```

Targeted retest checked the actual heading and passed.

No product defect confirmed.

### P003 — Closed as case-sensitive expected heading mismatch — Open needs section

Initial live-log record expected `Open Needs`.

Resolution:

The actual fixed heading is:

```text
## Open needs
```

This matches `REPORT_HEADINGS` in `idea_spark/export.py`.

Targeted retest passed.

No product defect confirmed.

### P004 — Closed as expected error path — JSON export

Initial live-log record expected `format=json` to succeed.

Resolution:

The plugin is currently designed for deterministic Markdown export only. `format=json` should fail with a structured error.

Targeted retest confirmed expected behavior:

```text
rc=1
stdout={"error": "unsupported export format", "format": "json", "success": false}
```

No product defect confirmed.

Potential improvement, not a defect: add a schema enum or clearer CLI help so agents do not infer JSON export support from the `format` parameter.

### P005 — Closed as static shell expectation mismatch — dashboard room page

Initial live-log record expected the room title to be server-rendered into `/room/<room_id>`.

Resolution:

`/room/<room_id>` serves a static shell. Room data is loaded client-side from `/api/rooms/<room_id>/snapshot` or SSE. The static room page is expected to contain the room id / shell, not necessarily the room title.

Targeted retest passed:

```text
/room/<room_id> contains room id: true
/api/rooms/<room_id>/snapshot contains room id, messages, artifacts, gates: true
/api/rooms/<room_id>/events?once=1 emits snapshot event: true
```

No product defect confirmed.

### P006 — Closed as wrong dashboard endpoint — room detail API

Initial live-log record called:

```text
/api/rooms/<room_id>
```

and got 404.

Resolution:

The implemented room detail API endpoint is:

```text
/api/rooms/<room_id>/snapshot
```

Targeted retest passed.

No product defect confirmed.

## Raw first-run failure log

The following failures were recorded immediately during testing before targeted retest clarified them:

```text
P001 artifact_link: relation=challenges rejected as invalid.
P002 export: expected heading '# Idea-Spark Room Export' but actual was '# Idea-Spark Room Report'.
P003 export: expected heading 'Open Needs' but actual was 'Open needs'.
P004 export: expected json export success but markdown-only implementation rejected format=json.
P005 dashboard: expected room title in static shell.
P006 dashboard: called /api/rooms/<room_id> instead of /api/rooms/<room_id>/snapshot.
P007 status: counts.open_needs remains 1 after resolving the only need.
```

---

## Realistic delegated-room scenario test — 20260614_192310

Status: completed

Test DB: `/tmp/idea_spark_delegated_room_20260614_192310.sqlite3`
Room: `delegated-flow-20260614_192310`
Payload directory: `/tmp/idea_spark_delegated_room_payloads_20260614_192310`
Dashboard port: `8879`

### Live log

- Started delegated-room scenario test.
- R1 launched `PriorArtBreaker` and `ExperimentPlanner` with `toolsets=["terminal", "file", "skills"]`; both joined, wrote typed artifacts, links, and messages.
- R2 launched `AuthorAdvocate` with explicit `payload_scratch_dir`; it joined, wrote `Rebuttal`, `RevisionPlan`, `OpenNeed`, links, and message without writing repo-root payloads.
- R3 launched `Gatekeeper` with explicit `payload_scratch_dir`; it joined, wrote `ScoreCard`, `MetaReview`, links, message, and terminal gate `gate_ea12c3a77568` with decision `needs_more_evidence`.
- Final room status: `gated`, `has_terminal_gate=true`, participants=4, messages=4, artifacts=12, gates=1.

### P008 — important — delegated-task payload hygiene / prompt-skill contract

**Summary:** In the realistic delegated-room flow, child agents wrote temporary CLI payload JSON files into the repository root. Follow-up check confirms this was **not** caused by omitting the `skills` toolset: both R1 child tasks were launched with `toolsets=["terminal", "file", "skills"]`, and the child traces show `skill_view` calls. The more precise root cause is that the parent prompt did not pass the temp `PAYLOAD_DIR` to children, and the bundled Idea-Spark skill's child checklist does not make a scratch payload directory / “never write payloads to workspace root” a hard requirement.

**Evidence:**

```text
Parent delegate_task toolsets for both R1 children:
["terminal", "file", "skills"]

Child trace evidence:
- PriorArtBreaker trace includes skill_view for the Idea-Spark skill.
- ExperimentPlanner trace includes skill_view calls, including the Idea-Spark skill.

Parent context passed to children:
- Workspace: /home/xu/project/autosci-delphi/idea-spark
- PAYLOAD_DIR: not passed

Repo-root payload files observed:
?? experiment_planner_artifact_read_all.json
?? experiment_planner_artifact_verify.json
?? experiment_planner_benchmark_requirement.json
?? experiment_planner_experiment_plan.json
?? experiment_planner_join.json
?? experiment_planner_link_benchmark_to_rubric.json
?? experiment_planner_link_plan_to_idea.json
?? experiment_planner_message_post.json
?? experiment_planner_message_read.json
?? experiment_planner_status.json
?? link_evidence_supports_objection.json
?? link_objection_critiques_ideacard.json
?? novelty_objection_r1.json
?? prior_art_breaker_artifact_read_all.json
?? prior_art_breaker_join.json
?? prior_art_breaker_message_r1.json
?? prior_art_breaker_status.json
?? prior_art_breaker_verify_read.json
?? prior_art_evidence_r1.json
```

**Impact:** Real old-flow use with several agents can leave many untracked `*_join.json`, `*_message_post.json`, and link payload files in the project tree if the parent prompt only gives a workspace path and says to create JSON payload files.

**Recommended fix / mitigation:** Applied in workspace: the bundled skill child prompt checklist and examples now require a `payload_scratch_dir` field in every CLI-first child prompt, e.g. `/tmp/idea_spark_<run_id>/<agent_id>/`, and explicitly forbid writing transient payload JSON to the workspace root. Parent prompts should pass that directory. Optional future improvement: add a helper CLI mode that accepts compact inline JSON safely or creates managed temp payloads.

### P009 — minor — round_wait payload ergonomics

**Summary:** During the delegated-room flow, a parent-style `idea_spark_round_wait` call with `room_id`, `round_id`, `expected_agents`, and `timeout_s` failed because `phase` is also required.

**Evidence:**

```text
{"error": "missing required field: phase", "success": false}
```

**Impact:** Old-flow parent controllers may naturally treat `round_id` as the barrier key and forget `phase`; the structured error is clear, but examples should make the required `phase` field hard to miss.

**Recommended fix / mitigation:** Ensure bundled examples and child/parent prompt templates always include both `round_id` and `phase` in `idea_spark_round_wait` payloads. Consider schema/help text saying phase is required for transcript/barrier labeling.

### P010 — important — round_wait phase/barrier mismatch in realistic multi-role rounds

**Summary:** In the delegated-room old-flow scenario, both r1 reviewers successfully joined and posted messages, but parent `idea_spark_round_wait` with a shared `phase="review"` returned timeout with `arrived_agents=[]` because the two child messages used role-specific phases (`novelty_attack` and `feasibility_attack`).

**Evidence:**

```text
round_wait payload:
{"room_id":"delegated-flow-20260614_192310","round_id":"r1","phase":"review","expected_agents":["prior-art-breaker","experiment-planner"],"timeout_s":1}

round_wait observed:
{"arrived_agents": [], "missing_agents": ["prior-art-breaker", "experiment-planner"], "status": "timeout", "success": true}

message_read immediately after showed:
- prior-art-breaker: round_id="r1", phase="novelty_attack", message_id=1
- experiment-planner: round_id="r1", phase="feasibility_attack", message_id=2
```

**Impact:** In realistic old-flow discussions, different roles naturally use different phase labels inside the same round. A parent controller can incorrectly conclude that no agents arrived even though room_status/messages prove they did.

**Recommended fix / mitigation:** Either (a) update examples/prompts so all agents in a barrier use the exact same `phase` value plus role-specific metadata, or (b) extend `idea_spark_round_wait` with an optional wildcard/list phase mode, e.g. omit `phase`, pass `phase="*"`, or pass `phases=[...]`.

### P011 — fixed in workspace — room creation must surface a dashboard link

**Summary:** User identified an old-flow UX gap: every time the parent creates an Idea-Spark room, the user should immediately receive a concrete dashboard room link, not only a `room_id` or implicit URL template.

**Backup comparison:** The provided backup at `/home/xu/backups/autosci-delphi/20260614_171954/idea-spark-working-tree.tgz` preserves the older live-room/dashboard workflow. Its bundled skill has a direct dashboard section with `/room/<room_id>` and a more tool-native minimal parent flow. The current CLI-first skill kept the dashboard URL template but did not make “copy the concrete room link to the user immediately after `room_create`” a hard parent step.

**Fix applied in this workspace:**

- `idea_spark_room_create` now returns `dashboard_url` and `room_url` on success.
- `idea_spark_room_create` accepts optional `dashboard_base_url`, so a parent that starts the dashboard on a non-default port can get the actual live-room URL back.
- Bundled skill, README, and examples now require the parent to surface `room_url` immediately after room creation.
- The same skill/example pass also captured adjacent old-flow hygiene found during testing: pass `payload_scratch_dir` to CLI-first children and use a shared `phase` for `round_wait` barriers.

**Regression coverage added:**

```text
tests/test_tools_room.py::test_room_create_returns_dashboard_room_url
tests/test_tools_room.py::test_room_create_accepts_custom_dashboard_base_url
tests/test_schema_contract.py::test_room_create_schema_exposes_dashboard_base_url
tests/test_cli.py::test_cli_call_room_lifecycle_with_json_files
```

### P012 — open — returned room link can be unavailable

**Summary:** User reported that the room link cannot be opened. This is distinct from P011: P011 made the system return and surface a link; P012 is that the surfaced link must be actually reachable, which is not guaranteed if the dashboard server is not running on that host/port or the URL was generated for the wrong port.

**Evidence:** Local follow-up probe showed one room URL can be reachable while another returned/generated URL is not:

```text
http://127.0.0.1:8765/room/link-smoke-room OK 200
http://127.0.0.1:8899/room/link-smoke-room FAIL URLError <urlopen error [Errno 111] Connection refused>
```

The failing case matches the current design risk: `idea_spark_room_create` can compute `room_url` from `dashboard_base_url`, but it does not prove that a dashboard process is alive at that URL.

**Impact:** In real use, the parent can satisfy “give me the room link” while still giving the user a dead link, especially after using a random/non-default dashboard port, after killing the dashboard process, or when WSL/host browser forwarding differs from the URL generated inside WSL.

**Recommended fix / mitigation:** Parent workflow should start the dashboard before room creation or immediately after it, health-check the concrete `/room/<room_id>` URL, and only then present it as openable. If the health check fails, report the room id plus the start-dashboard command instead of a dead link. Product-side options include returning `dashboard_checked`, `dashboard_reachable`, or a warning field from room creation, or adding a helper command that creates a room, starts/locates the dashboard, verifies the URL, and returns only a known-good link.
