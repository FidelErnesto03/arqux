# ArqUX Handlers

Total: **73** handlers

## Governance Budget (P1-R)

ArqUX classifies handlers into two categories:

### Governance Handlers (24-handler budget)

These 24 handlers manage the lifecycle of governance artifacts (blueprints, cycles, tasks, evidence, identities, sessions, projects, protocols). They are the canonical surface area that the governance model enforces.

| Module | Handlers | Count |
|---|---|---:|
| `blueprint` (governance subset) | `create`, `define`, `mature`, `ready`, `assign`, `claim`, `update`, `complete`, `fail`, `cancel`, `approve`, `re_delegate`, `block_for_architect`, `task`, `gate`, `ac` | 16 |
| `cycle` | `create`, `mature`, `close` | 3 |
| `protocol` | `adopt`, `release`, `pause`, `resume`, `cycle.mature` (overlap) | 4 |
| `evidence` | `record` | 1 |
| **Total governance budget** | | **24** |

### Utility Handlers (49 handlers)

The remaining 49 handlers are utility/read operations:

| Module | Handlers | Count |
|---|---|---:|
| `blueprint` (read) | `read`, `list` | 2 |
| `cortex` | `entry.add/delete/get/list/move/update`, `file.validate`, `learn`, `learn.elevate`, `read`, `render`, `render.diagram`, `render.validate_file`, `verify`, `write` | 15 |
| `cycle` (read) | `current`, `list` | 2 |
| `evidence` (read) | `list`, `read` | 2 |
| `identity` | `record` | 1 |
| `project` | `bind`, `init`, `lessons`, `status`, `unbind` | 5 |
| `session` | `close`, `context.get`, `context.set`, `resume`, `status` | 5 |
| `setup` | `plantuml` | 1 |
| `skill` | `convert`, `edit`, `evolve`, `import`, `list`, `record` | 6 |
| `task` (read) | `read`, `list` | 2 |
| `workspace` | `init`, `lessons`, `status` | 3 |
| **Total utility** | | **49** |

The 24-handler governance budget is a design constraint: adding a new governance handler requires removing one. Utility handlers can grow without bound.


## blueprint

| Handler | Description |
|---------|-------------|
| `blueprint.ac` | Verify one AC in §12. Fail triggers auto re-delegate (max 3). |
| `blueprint.block_for_architect` | Block for Architect manual review. |
| `blueprint.cancel` | Cancel a Blueprint. Governor-only. State → cancelled. |
| `blueprint.claim` | Executor claims the Blueprint. ready → in_progress + implicit executor assignment. |
| `blueprint.complete` | Declare execution complete. in_progress → done (single step). |
| `blueprint.create` | Create a new Blueprint from BLP_TEMPLATE.md in draft state. |
| `blueprint.execute` | Meta-handler: verify §3 preconditions, run §14 tasks, verify §12 ACs, mark complete. Supports dry_run. |
| `blueprint.fail` | Blueprint hit an obstacle. State → blocked. |
| `blueprint.list` | List Blueprints with optional filters. |
| `blueprint.read` | Read a full Blueprint (HCORTEX or CORTEX format). |
| `blueprint.ready` | Architect declares Blueprint ready for execution. draft → ready. |
| `blueprint.re_delegate` | Re-delegate after verification failure. Re-opens a done/blocked blueprint. |
| `blueprint.synthesize` | Guide mode: creates or finds the BLP and returns the next pending section. |
| `blueprint.task` | Update one task's checkbox in §14. Status: in_progress/completed. |
| `blueprint.update` | Update Blueprint progress with a note or refine a single section. |

### Blueprint state machine

```
draft → ready → in_progress → done
  │        │         │          ▲
  │        │         ├── blueprint.fail → blocked ── blueprint.re_delegate ──┐
  │        │         │                                                     │
  │        │         └── blueprint.block_for_architect → blocked           │
  │        │                                                               │
  └── blueprint.cancel → cancelled      (re_delegate reopens → in_progress)┘
```

| Transition | Handler | Notes |
|-----------|---------|-------|
| → `draft` | `blueprint.create`, `blueprint.synthesize` | Create from template; synthesize is guide-only. |
| `draft → ready` | `blueprint.ready` | **Gate:** refuses with `OUT-ERROR code=VALIDATION` while template placeholders (`_…_` markers from BLP_TEMPLATE.md) remain in the body. §18 `☐`/`✅` cells are quality-gate state and excluded from the scan (BLP-009). Status stays `draft` on rejection. |
| `ready → in_progress` | `blueprint.claim` | Implicit executor assignment. |
| `in_progress → done` | `blueprint.complete`, `blueprint.execute` | `complete` validates §12 ACs and §14 tasks are closed (`EXECUTION_INCOMPLETE` otherwise). |
| `* → blocked` | `blueprint.fail`, `blueprint.block_for_architect` | `fail` records a reason. |
| `blocked/done → in_progress` | `blueprint.re_delegate` | Max 3 verification loops; `done` and `cancelled` are terminal for `fail`/`cancel`. |
| `* → cancelled` | `blueprint.cancel` | Governor-only. Terminal. |
| (no transition) | `blueprint.ac`, `blueprint.task`, `blueprint.update` | In-flight bookkeeping: §12 checkboxes, §14 task checkboxes, progress notes. |

## cortex

| Handler | Description |
|---------|-------------|
| `cortex.entry.add` | Add a new entry to a .cortex file. Stores the entry under the
requested name; on `sigil:name` collision it appends a `_NNNN` suffix and
reports `renamed:<requested>-><assigned>` plus `requested`/`renamed` fields
(BLP-007 — no silent renames). Selectors support a trailing `*` prefix
wildcard (e.g. `$1/DOM:mi_app*`). |
| `cortex.entry.delete` | Delete an entry matching a CORTEX selector from a .cortex file. |
| `cortex.entry.get` | Read entries matching a CORTEX selector from a .cortex file. |
| `cortex.entry.list` | List entries in a .cortex file, optionally filtered. |
| `cortex.entry.move` | Move an entry between sections in a .cortex file. |
| `cortex.entry.update` | Update an entry selected by a CORTEX selector. |
| `cortex.file.validate` | Scan a .cortex file for duplicate entry names and optionally fix them. |
| `cortex.learn` | Scan a project brain through the CODEC-CORTEX Learning Engine.
Returns scored entries and elevation candidates. |
| `cortex.learn.elevate` | Elevate a learning candidate (SES->LNG or LNG->KNW).
Default is dry-run (shows diff without applying).
Pass apply=true with confirm_hash from a reviewed dry-run to write the elevation to brain.cortex. |
| `cortex.read` | Read and parse a .cortex file using CODEC-CORTEX. |
| `cortex.render` | Render a .cortex file to HCORTEX READ markdown. |
| `cortex.render.diagram` | Render a PlantUML diagram to SVG/PNG. Requires plantuml.jar. |
| `cortex.render.validate_file` | Validate all PUML blocks in a file. Returns D1-D5 checklist. |
| `cortex.ref` | Return a sigil's definition (name, type, risk, layer, fields).
Strictly read-only — never mutates governance state (BLP-007). |
| `cortex.verify` | Verify a .cortex file's structure using CODEC-CORTEX. |
| `cortex.write` | Write (atomically) a .cortex file from CORTEX source text. |

## cycle

| Handler | Description |
|---------|-------------|
| `cycle.close` | Close a cycle (no new tasks can be added). |
| `cycle.create` | Open a new cycle in the active project. |
| `cycle.current` | Get the currently active cycle. |
| `cycle.list` | List cycles in the active project. |
| `cycle.mature` | Mature a cycle (draft → ready). |

## evidence

| Handler | Description |
|---------|-------------|
| `evidence.list` | Query the evidence trail. |
| `evidence.read` | Read a single evidence event by ID. |
| `evidence.record` | Append an evidence entry to pulse.jsonl. |

## identity

| Handler | Description |
|---------|-------------|
| `identity.record` | Record a behavioral lesson into the agent's identity file. |

## project

| Handler | Description |
|---------|-------------|
| `project.bind` | Bind an agent identity to the current project with a role. |
| `project.init` | Initialize .arqux/ in a project directory and register it in the
workspace. Without `seed`, writes the validator-clean level-2 starter brain
(`templates/brain.cortex`); with `seed`, writes it verbatim. Registration
writes a real `DOM:<name>` entry into workspace `projects.cortex` (created
if absent) and reports `registered_in_workspace` honestly — `false` when no
workspace contains the project or the write fails. |
| `project.lessons` | List lessons local to the current project. |
| `project.status` | Active project status (cycles, tasks, agents). |
| `project.unbind` | Release an agent binding from the current project. |

## protocol

| Handler | Description |
|---------|-------------|
| `protocol.adopt` | Onboard an agent with a role. |
| `protocol.pause` | Suspend governance for the current session without losing state. |
| `protocol.release` | Fully detach an agent (clean exit, no orphans). |
| `protocol.resume` | Resume governance after a pause. |

## session

| Handler | Description |
|---------|-------------|
| `session.close` | Close the current session and write a portable SES entry to brain PULSE. |
| `session.context.get` | Read the current context pointer and return the formatted header. |
| `session.context.set` | Set the current session context pointer (project + scope + optional BLP). Validates project exists and returns the formatted header. |
| `session.resume` | Read the last SES entry from brain PULSE and restore the context. |
| `session.status` | Read SES metadata without restoring full context. |

## setup

| Handler | Description |
|---------|-------------|
| `setup.plantuml` | Download and install plantuml.jar to ~/.arqux/bin/. |

## skill

| Handler | Description |
|---------|-------------|
| `skill.convert` | Convert a skill from original format to CORTEX ultra-dense. |
| `skill.edit` | Edit (read, write, or section-edit) a skill file in .arqux/skills/. Without content: returns the skill content. With content but no section: atomically replaces the entire skill file. With content and section: replaces only that CORTEX section (e.g. $0, $1, $2.1). This is the governed alternative to direct file editing of skills. |
| `skill.evolve` | Apply an approved adaptation to a skill. Default is dry-run. |
| `skill.import` | Acquire a skill from external source, store original in originals/. |
| `skill.list` | List all available skills in .arqux/skills/. |
| `skill.record` | Record a deviation (ADA) when a skill does not match the real context. |

## task

| Handler | Description |
|---------|-------------|
| `task.claim` | An executor claims a task → status: in_progress. |
| `task.complete` | Mark a task done and record evidence. |
| `task.create` | Create a governed task in the current cycle. |
| `task.fail` | Mark a task blocked and record the cause. |
| `task.list` | List tasks with filters. |
| `task.read` | Read a task (CORTEX or HCORTEX format). |
| `task.update` | Update task progress, optionally change status. |

**Cycle resolution contract (BLP-006):** `task.read`, `task.claim`,
`task.update`, `task.complete`, `task.fail` and `task.run` resolve
`task_id` deterministically:

1. A path inside `.../cycles/CYCLE-XX` scopes the lookup to that cycle.
2. Without a derivable cycle, the project's current cycle wins.
3. Otherwise a single match in any other cycle is returned; multiple
   matches return `TASK_AMBIGUOUS` listing the candidate cycles —
   lookups never silently pick the first alphabetical cycle.


## workspace

| Handler | Description |
|---------|-------------|
| `workspace.init` | Initialize .arqux/ at the workspace root. |
| `workspace.lessons` | List lessons elevated to the meta-brain. |
| `workspace.status` | Workspace status (OUT-MIN by default). |

