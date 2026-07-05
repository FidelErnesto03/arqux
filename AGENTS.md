# AGENTS.md — Arqux

> Single entry point for any AI agent adopting this framework.
> If you are reading this, you are expected to be able to operate after this file alone.
> Format: CORTEX (machine-optimized). A human-readable HCORTEX version exists at `AGENTS.md`.

---

## 1. What Arqux is

Arqux is the minimum-viable governance framework for AI agent teams. It is **not** an orchestrator, a CI/CD system, or a project manager. It is a small protocol layer that lets multiple agents work in the same workspace without stepping on each other: a **governor** decides what to do, an **executor** does it and leaves evidence, an **auditor** reads everything but mutates nothing.

Every state mutation flows through a fixed budget of **24 MCP handlers** grouped in **6 modules**. There is no direct file editing of governance state — handlers are the interface, files are the storage. The framework persists state via the [CODEC-CORTEX](https://github.com/FidelErnesto03/codec-cortex) codec, which produces `.cortex` (machine-optimized) and `.md` (human-readable) files in sync.

You should adopt this framework when: you are working in a workspace with more than one agent, you need traceability of decisions, you need clean role separation, or you need cross-project learning. You should **not** adopt it for single-agent throwaway work, for CI/CD pipelines, or as a project manager.

## 2. How to detect Arqux

Walk up the directory tree from your current working directory. If you find a directory named `.arqux/` containing `manifest.cortex`, you are inside a governed workspace. If you also find a `.arqux/brain.cortex` in your immediate project directory, that project is governed too.

If no `.arqux/` is found, the workspace is not initialized. Ask the human whether to run `arqux init` or wait for instructions. **Do not** initialize without explicit confirmation.

## 3. STANDBY-FIRST

Every session begins in standby. There is no auto-recovery of context, no auto-binding to a project, no automatic handler invocation. Your **first response to the human must be an open question** — typically some variant of "What would you like me to work on?".

When the human gives you a goal, you may invoke `workspace.status` and `project.status` to load context. Do not invoke any handler that mutates state (`task.create`, `cycle.create`, `task.claim`, etc.) without explicit confirmation from the human or from a governor agent.

If the human says `@arqux:off`, you must fully detach: forget your identity binding, do not invoke governance handlers, and behave as if the framework does not exist. If the human says `@arqux:pause`, suspend governance without losing state — you can resume with `@arqux:resume`.

## 4. Handlers — full table (24, fixed budget)

| # | Handler | Signature | Purpose |
|---|---|---|---|
| 1 | `workspace.init` | `(path?)` | Initialize `.arqux/` at workspace root |
| 2 | `workspace.status` | `(verbose?)` | Workspace status (OUT-MIN by default) |
| 3 | `workspace.lessons` | `(project?)` | List lessons elevated to meta-brain |
| 4 | `project.init` | `(name, path?)` | Initialize `.arqux/` in a project, register in workspace |
| 5 | `project.bind` | `(agent_id, role)` | Bind an agent identity to current project |
| 6 | `project.unbind` | `(agent_id)` | Release an agent binding |
| 7 | `project.status` | `()` | Active project status (cycles, tasks, agents) |
| 8 | `project.lessons` | `()` | List lessons local to current project |
| 9 | `cycle.create` | `(name?, description?)` | Open a new cycle in the active project |
| 10 | `cycle.list` | `(status?)` | List cycles in active project |
| 11 | `cycle.current` | `()` | Get the currently active cycle |
| 12 | `cycle.close` | `(cycle_id, summary?)` | Close a cycle (no new tasks can be added) |
| 13 | `task.create` | `(obj, pre?, proc?, ac?, blk?, assignee?, complexity?)` | Create a governed task in current cycle |
| 14 | `task.claim` | `(task_id)` | An executor claims a task → status: in_progress |
| 15 | `task.update` | `(task_id, note, status?)` | Update task progress, optionally change status |
| 16 | `task.complete` | `(task_id, evidence?)` | Mark task done, record evidence |
| 17 | `task.fail` | `(task_id, reason)` | Mark task blocked, record cause |
| 18 | `task.read` | `(task_id, format?)` | Read a task (CORTEX or HCORTEX) |
| 19 | `task.list` | `(status?, assignee?, cycle?)` | List tasks with filters |
| 20 | `evidence.record` | `(task_id, kind, payload)` | Append evidence entry to `pulse.jsonl` |
| 21 | `evidence.list` | `(task_id?, cycle?, since?, limit?)` | Query evidence trail |
| 22 | `evidence.read` | `(event_id)` | Read a single evidence event |
| 23 | `protocol.adopt` | `(agent_id, role)` | Onboard an agent with a role |
| 24 | `protocol.release` | `(agent_id)` | Fully detach an agent (clean exit, no orphans) |

(`protocol.pause` / `protocol.resume` are also exposed but counted as one logical surface — they do not mutate persisted state, only in-process session state.)

## 5. Roles and permissions

| Role | Allowed handler prefixes | Description |
|---|---|---|
| `governor` | `workspace.*`, `project.*`, `cycle.*`, `task.create`, `task.complete`, `task.fail`, `evidence.*`, `protocol.*` | One per workspace. Decides, assigns, approves, closes. |
| `executor` | `task.claim`, `task.update`, `task.complete`, `task.fail`, `task.read`, `task.list`, `evidence.record`, `evidence.list`, `evidence.read`, `protocol.release` (self) | Picks up tasks and executes them. Cannot create cycles or tasks. |
| `auditor` | `*.read`, `*.list`, `*.status`, `*.lessons` (read-only handlers) | Read-only. Cannot mutate any state. |

Enforcement is at the handler level. If you call a handler outside your role, the system rejects with `PERMISSION_DENIED` and **does not** record the attempt as evidence — the rejection itself is the protocol. There are no exceptions, no escape hatches, no "consultative mode".

If you are the first agent to call `workspace.init` on a fresh workspace, you become the governor by default. Subsequent agents must call `protocol.adopt` with a role assigned by the governor.

## 6. Task format (CORTEX)

Tasks are the atomic unit of work. Each task lives in `.<product>/>cycles/<CYCLE-NN>/tasks/T-NNN.cortex` (machine) with a synced `.md` (human). The CLI `cortex` (provided by CODEC-CORTEX) maintains bidirectional sync.

Minimum CORTEX task:

```
---
id: T-001
status: draft
governor: governor
assignee: executor
priority: medium
complexity: standard
cycle: CYCLE-01
created: 2026-07-04T10:00:00Z
updated: 2026-07-04T10:00:00Z
---

# OBJ
One-sentence objective.

# PRE
- Precondition 1
- Precondition 2

# PROC
1. Step one
2. Step two

# AC
- Acceptance criterion 1
- Acceptance criterion 2

# BLK
- Blocking condition → HALT_AND_REPORT
```

Status transitions: `draft → open → in_progress → review → done`. From any state: `→ blocked` (recoverable) or `→ cancelled` (terminal). No `validation`, no `approved`, no `superseded` — keep it simple.

## 7. MCP configuration

Add this single block to your MCP client's settings (Gemini / Qwen / Claude / VS Code / Cursor / Hermes):

```json
{
  "mcpServers": {
    "arqux": {
      "command": "arqux",
      "args": ["serve"]
    }
  }
}
```

No bash scripts. No absolute paths. The `arqux` command is provided by `pip install arqux`.

## 8. CORTEX-OUT output protocol

Your responses to the human (and to other agents) should follow CORTEX-OUT to minimize tokens and maximize clarity. Pick the profile that matches the context:

| Profile | When to use | Example |
|---|---|---|
| `OUT-MIN` | Quick status acks, no detail needed | `OK T-001 in_progress` |
| `OUT-WORK` | Work updates, deliverables, evidence of progress | `DONE T-001 evidence=E-007 coverage=87%` |
| `OUT-AUDIT` | Architecture reviews, decision logs | `REVIEW cycle=CYCLE-01 risk=low rationale=...` |
| `OUT-FULL` | Detailed explanations to humans | (full prose, no compression) |
| `OUT-ERROR` | Failures, blockers, permission denials | `ERROR code=PERMISSION_DENIED handler=task.create reason=executor_role` |

Default profile: pick the smallest one that conveys the necessary information. A governor reviewing architecture may use `OUT-AUDIT`; an executor completing a task may use `OUT-WORK`; a quick acknowledgement is `OUT-MIN`. Never use `OUT-FULL` for routine updates — that wastes tokens.

## 9. The project brain — shared mind for concurrent agents

`brain.cortex` is the **single shared mind of a project**. Every agent bound to the project reads and writes the same brain. This is how multiple agents working concurrently share one project mind: there is no per-agent brain, no per-cycle brain, no separate pulse file — there is ONE brain per project, and every handler that mutates project state writes to it.

The brain has nine canonical sections:

| Section | Purpose | Written by |
|---|---|---|
| `# FOCUS` | One-sentence current focus | Governor |
| `# OBJECTIVES` | Stable project goals (not tasks) | Governor |
| `# SESSIONS` | Agents bound to the project (agent, role, status) | `project.bind`, `project.unbind` |
| `# HANDOFFS` | Chronological log of work handed between agents | Task handlers on transitions |
| `# PULSE` | Append-only event trace (replaces `pulse.jsonl`) | `evidence.record`, `task.complete`, `task.fail` |
| `# LESSONS` | Contextual lessons (project-specific) | Governor (via evidence) |
| `# ACTIVE_CONTEXT` | Currently active cycle/task | Task handlers |
| `# RISKS` | Project-specific risks | Governor |
| `# CONCURRENCY` | Optimistic-lock state (`brain_version`) | Every write handler (automatic) |

**Why one brain, not many files:** if pulse, handoffs, and sessions lived in separate files, an agent reading the project state would have to open N files and reconcile them. With one brain, the agent reads ONE file and sees the full project mind. This is essential for concurrent work: every agent has the same view.

**Concurrency model:** the brain has a `brain_version` counter in its frontmatter. Every mutation bumps it and records the last writer. Before writing, a handler should read the current version; if the version changed since the agent's last read, the handler re-reads and retries. In this minimal implementation, handlers bump the version on every write without retry logic — full optimistic locking is the handler's responsibility (see `state.brain_version`).

**What does NOT live in the brain:**
- Task definitions (`.cortex` per task, in `cycles/<CYCLE>/tasks/`)
- Cycle metadata (`cycle.cortex` per cycle)
- Identity behavioral lessons (in the installed package's `agents/<identity>.cortex`)
- Workspace meta-brain (separate file at the workspace level)

## 10. HCORTEX — a form of writing markdown

HCORTEX is **a form of writing markdown** oriented to facilitate reading, understanding, and organization, while minimizing token consumption. It is NOT a separate format — it is a discipline for writing markdown that humans read efficiently.

### The HCORTEX discipline

1. **One section per idea.** Each `#` heading introduces exactly one concept. No multi-idea sections.
2. **Lists over prose.** Prefer `- ` bullets to paragraphs. Each bullet is a complete, scannable unit.
3. **Bold the key term.** In each bullet, `**bold**` the noun or verb the reader is looking for. The rest is context.
4. **Tables for comparisons.** Two or more items with the same attributes → table. Never repeat the same prose structure.
5. **No redundant headers.** If the body is one line, do not add a header above it — the line stands alone.
6. **Frontmatter as metadata.** All machine-readable fields (id, status, timestamps) go in YAML frontmatter. The body is for humans.
7. **No decorative tokens.** No emojis, no horizontal rules between every section, no "------" separators. Whitespace is enough.
8. **Short sentences.** ≤25 words per sentence. If a sentence is longer, split it.
9. **Code blocks for commands.** A command to type → fenced code block. Never inline backticks for multi-word commands.
10. **Round-trip with CORTEX.** Every HCORTEX file has a `.cortex` twin. The CLI `cortex to-machine` regenerates the machine form. Editing one propagates to the other.

### Example: HCORTEX vs. plain markdown

Plain markdown (verbose, ~80 tokens):
```markdown
# Task Status

The task T-001 is currently in progress. It was claimed by the executor agent
identified as "jarvis" at the timestamp 2026-07-04T10:00:00Z. The task is part
of cycle CYCLE-01, which is the first cycle of the project. The task objective
is to implement the health check endpoint.
```

HCORTEX (compact, ~25 tokens):
```markdown
# T-001

- **status:** in_progress
- **assignee:** jarvis
- **cycle:** CYCLE-01
- **objective:** implement health check endpoint
```

Both convey the same information. HCORTEX uses ~30% of the tokens and is faster to scan.

### When to use HCORTEX

- Always, for `.md` files (the human-readable twin of a `.cortex`).
- For agent responses to humans when the human needs structured information (use `OUT-WORK` or `OUT-AUDIT` profiles, which follow the same discipline).
- NOT for prose-heavy explanations to humans — use `OUT-FULL` for those.

## 11. CODEC-CORTEX integration

State is persisted via CODEC-CORTEX. You should never directly edit `.cortex` or `.md` files — handlers do that, and the CLI `cortex` keeps the two formats in sync.

Essential `cortex` commands (provided by the codec-cortex package):

- `cortex verify <file.cortex>` — validates structure
- `cortex to-human <file.cortex>` — emits the `.md` form
- `cortex to-machine <file.md>` — emits the `.cortex` form
- `cortex diff <file>` — shows drift between the two forms

If `cortex verify` fails on a file produced by a handler, that is a **bug in the handler** — report it as a task (`task.create` with `complexity: bug`).

## 12. Learning layers — behavioral vs. contextual

The framework has three learning layers, kept strictly separate. An agent conflating them is a design bug.

| Layer | Where it lives | What it captures | Scope | Example |
|---|---|---|---|---|
| **Behavioral** (identity) | `agents/<identity>.cortex` in the installed package | How a role should act, regardless of project | Cross-project, role-scoped | "Always check permissions before creating a task" (governor lesson) |
| **Contextual** (project) | `.<product>/brain.cortex` → `# LESSONS` section | What was learned about THIS project | This project only | "We use Redis for caching in this project" |
| **Global** (workspace) | `.<product>/meta-brain.cortex` | Patterns that apply across all projects | Workspace-wide | "Python 3.10+ is our baseline" |

### Behavioral lessons (identity)

- Live in the installed package, NOT in any project directory.
- A governor in project A shares behavioral lessons with a governor in project B.
- Examples: decision-making patterns, preferred review cadence, how to phrase handoffs.
- Written by the framework maintainers (or by a future `agent.learn` handler). Project agents do NOT mutate identity files.

### Contextual lessons (project)

- Live in the project brain's `# LESSONS` section.
- Apply to THIS project only. A lesson about project A's architecture does not leak into project B.
- Examples: "this project uses Redis, not Memcached", "the test suite takes 8 minutes, plan accordingly", "module X is deprecated, do not extend it".
- Written by the governor (typically after a cycle retrospective). Executors record candidate lessons as evidence; the governor promotes them to the brain.

### Global lessons (workspace)

- Live in the workspace meta-brain's `# LESSONS` section.
- Apply across all projects in the workspace.
- Examples: "we standardized on pytest", "every project must have a health check endpoint".
- Elevated from project brains by the governor when a lesson proves to apply broadly.

### Elevation flow

```
evidence.record (kind=note, payload="candidate lesson")
        ↓
project brain # LESSONS  (governor promotes after retrospective)
        ↓
meta-brain # LESSONS  (governor elevates if cross-project)
```

**Anti-pattern:** an executor writing a behavioral lesson ("I should always run tests before completing") into the project brain. That is a behavioral lesson — it belongs in the executor's identity file, not the project brain.

## 13. MCP is the only governance interface

Files with the `.cortex` extension (CORTEX protocol) — including `brain.cortex`, `meta-brain.cortex`, `manifest.cortex`, `projects.cortex`, `cycle.cortex`, `T-NNN.cortex`, and `agents/<identity>.cortex` — are **administered and managed exclusively via the framework's MCP handlers**. Direct editing of these files by agents or humans is forbidden.

- ✅ To mutate the project brain → call `project.bind`, `task.complete`, `task.fail`, `evidence.record`, etc.
- ✅ To mutate a task → call `task.create`, `task.update`, `task.complete`, `task.fail`.
- ✅ To mutate a cycle → call `cycle.create`, `cycle.close`.
- ✅ To mutate the meta-brain → call `workspace.lessons` (read) — elevation is via handlers.
- ❌ To "fix" a brain section → do NOT open `brain.cortex` in an editor. If a section is wrong, the handler that wrote it has a bug — file a task.
- ❌ To "add a quick lesson" → do NOT append to `# LESSONS` directly. Use `evidence.record` with `kind=note` and let the governor promote it.

The handler is the interface. The file is the storage. This separation is what guarantees that every mutation is permission-checked, versioned, and traceable.

## 14. Dogfooding rule

This framework governs its own development. Every feature in this repository is implemented as a governed task in `.arqux/cycles/`. If you find the framework cannot govern its own development — because a handler is missing, because the task format is insufficient, because the permission model blocks you — **that is a bug in the framework, not an invalid use case**. Iterate the framework until it can.

---

*End of AGENTS.md. If you read this far, you can operate.*
