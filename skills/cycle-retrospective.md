# cycle-retrospective — Run a post-cycle audit and elevate lessons

## When to use
- A cycle has just been closed (`cycle.close`).
- You are an auditor reviewing a completed cycle.
- You are a governor deciding which lessons to elevate to the meta-brain.

## What to do

1. **Read the cycle's evidence trail.**
   Call `evidence.list` with the cycle ID. Read every event with
   `evidence.read`. Use the `OUT-AUDIT` profile for your responses.
   All events live in the project brain's `# PULSE` section — there is
   no separate `pulse.jsonl` file.

2. **Categorize events.**
   Group events into:
   - **Decisions** — `kind=decision` events. Capture the rationale.
   - **Artifacts** — `kind=artifact` events. List what was produced.
   - **Metrics** — `kind=metric` events. Summarize the values.
   - **Blockers** — `kind=blocker` events. Note recurring patterns.

3. **Identify lessons — and classify each as behavioral or contextual.**

   This is the critical step. The framework has THREE learning layers,
   kept strictly separate. Conflating them is a design bug.

   ### Behavioral lessons (identity-scoped)
   - **What they capture:** how a role should act, regardless of project.
   - **Where they live:** `agents/<identity>.cortex` in the installed package.
   - **Scope:** cross-project, role-scoped. A governor in project A shares
     behavioral lessons with a governor in project B.
   - **Examples:**
     - "Always check permissions before creating a task" (governor)
     - "Run the full test suite before calling task.complete" (executor)
     - "When auditing, sample at least 10% of evidence events" (auditor)
   - **Who writes them:** the framework maintainers, or a future
     `agent.learn` handler. Project agents do NOT mutate identity files.
     If you discover a behavioral lesson, file it as a task
     (`task.create` with `complexity: bug` or `complexity: standard`)
     proposing the identity update — do not edit the identity file.

   ### Contextual lessons (project-scoped)
   - **What they capture:** what was learned about THIS project.
   - **Where they live:** the project brain's `# LESSONS` section.
   - **Scope:** this project only. A lesson about project A's architecture
     does not leak into project B.
   - **Examples:**
     - "This project uses Redis for caching, not Memcached"
     - "The test suite takes 8 minutes — plan cycle exits accordingly"
     - "Module X is deprecated; do not extend it. New code goes in module Y."
     - "The CI pipeline fails on Python 3.9 — we target 3.10+."
   - **Who writes them:** the governor, after a cycle retrospective.
     Executors record candidate lessons as evidence (`kind=note`); the
     governor promotes them to the brain's `# LESSONS` section.

   ### Global lessons (workspace-scoped)
   - **What they capture:** patterns that apply across all projects.
   - **Where they live:** the workspace meta-brain's `# LESSONS` section.
   - **Scope:** workspace-wide.
   - **Examples:**
     - "We standardized on pytest"
     - "Every project must have a health check endpoint"
     - "Python 3.10+ is our baseline"
   - **Who writes them:** the governor elevates a contextual lesson to
     global when it proves to apply broadly. The elevation is itself a
     decision (record it via `evidence.record` with `kind=decision`).

4. **For each lesson, decide its destination.**
   Ask:
   - Does this describe how a ROLE should act? → **behavioral** (propose
     identity update via a task — do not edit the identity file).
   - Does this describe a fact about THIS project? → **contextual**
     (promote to the project brain's `# LESSONS`).
   - Does this describe a fact that applies to ALL projects? → **global**
     (elevate to the meta-brain's `# LESSONS`).

5. **Elevate contextual lessons to the project brain.**
   The governor promotes a candidate lesson (recorded as evidence) to
   the brain's `# LESSONS` section. This is done via the appropriate
   handler — never by direct file editing.

6. **Elevate cross-project lessons to the meta-brain.**
   If a contextual lesson applies broadly, the governor elevates it to
   the workspace meta-brain. Record the elevation as a decision in the
   project brain's `# PULSE` section.

7. **Produce a retrospective summary.**
   Write a short summary (≤500 words) covering:
   - Cycle goals vs. outcomes
   - Key decisions and their outcomes
   - Metrics summary
   - Lessons classified by layer (behavioral / contextual / global)
   - Risks identified

8. **Close the cycle (if not already closed).**
   If the cycle is still open, call `cycle.close` with the summary.

## Anti-patterns to avoid

- ❌ Writing a behavioral lesson ("I should always run tests before
  completing") into the project brain. That belongs in the executor's
  identity file, not the project brain.
- ❌ Editing `agents/<identity>.cortex` directly. Identity files are
  managed by framework maintainers (or a future handler), not by
  project agents. Propose identity updates via tasks.
- ❌ Writing a project-specific fact ("we use Redis") into the
  meta-brain. That is contextual, not global — it belongs in the
  project brain.
- ❌ Skipping the classification step and dumping all lessons into one
  layer. The separation exists so that a governor moving from project
  A to project B carries behavioral lessons but not contextual ones.

## References
- `AGENTS.md` §9 (The project brain — shared mind for concurrent agents)
- `AGENTS.md` §12 (Learning layers — behavioral vs. contextual)
- `AGENTS.md` §13 (MCP is the only governance interface)
