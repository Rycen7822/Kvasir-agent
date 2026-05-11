---
name: writing-plans
description: Write DeepScientist-aware implementation, experiment-roadmap, code-only, and formal-command plans with TDD and durable quest outputs.
version: 1.1.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
metadata:
  hermes:
    tags: [planning, design, implementation, workflow, documentation]
    category: software-development
    related_skills: [subagent-driven-development, test-driven-development, requesting-code-review]
skill_role: companion
---

> Codex adapter note: this is a Codex-packaged DeepScientist support skill adapted from the user-local Hermes skill library. Use `scripts/dsctl.py call <ds_tool_name> --json ... --format json` for durable quest state, memory, artifacts, and quest-local shell execution. Load it only when it is the relevant companion to the active stage.

# Writing Implementation Plans

## Overview

Write comprehensive implementation plans assuming the implementer has zero context for the codebase and questionable taste. Document everything they need: which files to touch, complete code, testing commands, docs to check, how to verify. Give them bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume the implementer is a skilled developer but knows almost nothing about the toolset or problem domain. Assume they don't know good test design very well.

**Core principle:** A good plan makes implementation obvious. If someone has to guess, the plan is incomplete.

## When to Use

**Always use before:**
- Implementing multi-step features
- Breaking down complex requirements
- Delegating to subagents via subagent-driven-development

**Don't skip when:**
- Feature seems simple (assumptions cause bugs)
- You plan to implement it yourself (future you needs guidance)
- Working alone (documentation matters)

## Bite-Sized Task Granularity

**Each task = 2-5 minutes of focused work.**

Every step is one action:
- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code to make the test pass" — step
- "Run the tests and make sure they pass" — step
- "Commit" — step

**Too big:**
```markdown
### Task 1: Build authentication system
[50 lines of code across 5 files]
```

**Right size:**
```markdown
### Task 1: Create User model with email field
[10 lines, 1 file]

### Task 2: Add password hash field to User
[8 lines, 1 file]

### Task 3: Create password hashing utility
[15 lines, 1 file]
```

## Plan Document Structure

### Header (Required)

Every plan MUST start with:

```markdown
# [Feature Name] Implementation Plan

> **For Codex:** implement this plan task-by-task with the available Codex editing, testing, and delegation workflow.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

### Task Structure

Each task follows this format:

````markdown
### Task N: [Descriptive Name]

**Objective:** What this task accomplishes (one sentence)

**Files:**
- Create: `exact/path/to/new_file.py`
- Modify: `exact/path/to/existing.py:45-67` (line numbers if known)
- Test: `tests/path/to/test_file.py`

**Step 1: Write failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

**Step 2: Run test to verify failure**

Run: `pytest tests/path/test.py::test_specific_behavior -v`
Expected: FAIL — "function not defined"

**Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

**Step 4: Run test to verify pass**

Run: `pytest tests/path/test.py::test_specific_behavior -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Writing Process

### Step 1: Understand Requirements

Read and understand:
- Feature requirements
- Design documents or user description
- Acceptance criteria
- Constraints

### Step 2: Explore the Codebase

Use Codex tools to understand the project:

```python
# Understand project structure
search_files("*.py", target="files", path="src/")

# Look at similar features
search_files("similar_pattern", path="src/", file_glob="*.py")

# Check existing tests
search_files("*.py", target="files", path="tests/")

# Read key files
read_file("src/app.py")
```

### Step 3: Design Approach

Decide:
- Architecture pattern
- File organization
- Dependencies needed
- Testing strategy

### Step 4: Write Tasks

Create tasks in order:
1. Setup/infrastructure
2. Core functionality (TDD for each)
3. Edge cases
4. Integration
5. Cleanup/documentation

### Step 5: Add Complete Details

For each task, include:
- **Exact file paths** (not "the config file" but `src/config/settings.py`)
- **Complete code examples** (not "add validation" but the actual code)
- **Exact commands** with expected output
- **Verification steps** that prove the task works

### Step 6: Review the Plan

Check:
- [ ] Tasks are sequential and logical
- [ ] Each task is bite-sized (2-5 min)
- [ ] File paths are exact
- [ ] Code examples are complete (copy-pasteable)
- [ ] Commands are exact with expected output
- [ ] No missing context
- [ ] DRY, YAGNI, TDD principles applied

### Step 7: Save the Plan

```bash
mkdir -p docs/plans
# Save plan to docs/plans/YYYY-MM-DD-feature-name.md
git add docs/plans/
git commit -m "docs: add implementation plan for [feature]"
```

### DeepScientist experiment roadmap variant

When the plan is for a DeepScientist quest's experiment execution rather than a normal software feature (see `references/deepscientist-experiment-roadmaps.md` for the session-tested checklist):

1. Load the relevant DeepScientist stage skill and follow the Codex-native operation boundary: use Codex-native tools for routine shell/Git/Python checks, and use `ds_bash_exec` only for formal evidence commands that need quest-local provenance. Use `ds_artifact_record` / `ds_memory_write` for durable outputs.
2. Read the user's requested source order exactly. For split research ideas, read the top-level `idea/*foundational_report.md` / index first, then active docs such as `paper_main.md`, `experiment_protocol.md`, `implementation_spec.md`, appendix/theory, related work, risk register, and download/resource manifest.
3. Save the roadmap under the quest's requested experiment directory, commonly `experiments/EXPERIMENT_EXECUTION_PLAN.md`, not only in chat.
4. Structure it as an ordered execution pipeline: preflight/baseline/resource gate, engineering scaffold, data split manifest, candidate/floorplan enumeration, trajectory extraction, chart/model-specific fitting, score implementation, sanity checks, main benchmark, statistics/robustness, retrofit/recoverability, appendix experiments, and paper-facing packaging.
5. Include explicit gates, required run artifacts, resource/model/data paths, protocol split boundaries, verification commands, and the first concrete implementation task.
6. Verify the written markdown with at least: required source-doc references present, all phase IDs present, all gates present, code-fence balance, display-math balance, and table consistency.
7. Record a quest memory and milestone artifact pointing to the roadmap and verification summary.

### DeepScientist code-only implementation variant

When the user asks to implement experiment code from an existing roadmap but explicitly says not to run experiments, use `references/deepscientist-code-only-implementation-passes.md`.

Key rules:

1. Create the requested code implementation plan first and make it the live control surface for code work.
2. Put source-document priority, allowed checks, and forbidden experiment actions in the plan itself.
3. Re-read and update the plan after each completed step; do not batch all checkbox updates at the end.
4. Make experiment-shaped CLI commands safe by default, typically writing `planned_not_executed` manifests instead of launching Phase 0/1A/2 runs.
5. Validate with code-only checks (`py_compile`, CLI help, pytest, lint, dry-run/fixture smoke), then record quest memory and a milestone that explicitly says no real experiment/model forward/training ran.

### DeepScientist formal experiment command handoff variant

When the user asks for a formal command document so they can run experiments step-by-step, write it as a quest-local file under the requested experiment directory (for example `experiments/正式实验命令.md`) instead of only answering in chat. See `references/deepscientist-formal-experiment-command-handoffs.md` for the session-tested checklist and pitfalls.

Key rules:

1. Re-read the execution roadmap, implementation plan, current CLI, and relevant configs before writing commands.
2. Verify actual CLI help for important commands and avoid documenting unsupported flags; if a desired flag is missing, document the current workaround and the required input file.
3. Order the document by the experiment phases (for DeepScientist, commonly E00-E12), starting with global shell variables and directory creation.
4. For every command block, state exactly what it produces and where outputs are saved; distinguish current dry-run/planned outputs from future real-run artifacts.
5. If current experiment-shaped CLI commands are `planned_not_executed` stubs, state that prominently so the user does not mistake command-plan JSON for real model evidence.
6. Include post-run validation commands and the exact information the user should provide back to DeepScientist for durable experiment recording.
7. Validate the written markdown for required phase tokens, key manifest paths, code-fence balance, and command/help consistency; record a quest memory and milestone.

## Principles

### DRY (Don't Repeat Yourself)

**Bad:** Copy-paste validation in 3 places
**Good:** Extract validation function, use everywhere

### YAGNI (You Aren't Gonna Need It)

**Bad:** Add "flexibility" for future requirements
**Good:** Implement only what's needed now

```python
# Bad — YAGNI violation
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
        self.preferences = {}  # Not needed yet!
        self.metadata = {}     # Not needed yet!

# Good — YAGNI
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
```

### TDD (Test-Driven Development)

Every task that produces code should include the full TDD cycle:
1. Write failing test
2. Run to verify failure
3. Write minimal code
4. Run to verify pass

See `test-driven-development` skill for details.

### Frequent Commits

Commit after every task:
```bash
git add [files]
git commit -m "type: description"
```

## Common Mistakes

### Vague Tasks

**Bad:** "Add authentication"
**Good:** "Create User model with email and password_hash fields"

### Incomplete Code

**Bad:** "Step 1: Add validation function"
**Good:** "Step 1: Add validation function" followed by the complete function code

### Missing Verification

**Bad:** "Step 3: Test it works"
**Good:** "Step 3: Run `pytest tests/test_auth.py -v`, expected: 3 passed"

### Missing File Paths

**Bad:** "Create the model file"
**Good:** "Create: `src/models/user.py`"

## Execution Handoff

After saving the plan, offer the execution approach:

**"Plan complete and saved. Ready to execute using subagent-driven-development — I'll dispatch a fresh subagent per task with two-stage review (spec compliance then code quality). Shall I proceed?"**

When executing, use the `subagent-driven-development` skill:
- Fresh `delegate_task` per task with full context
- Spec compliance review after each task
- Code quality review after spec passes
- Proceed only when both reviews approve

## Remember

```
Bite-sized tasks (2-5 min each)
Exact file paths
Complete code (copy-pasteable)
Exact commands with expected output
Verification steps
DRY, YAGNI, TDD
Frequent commits
```

**A good plan makes implementation obvious.**
