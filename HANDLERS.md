# ArqUX Handlers

Total: **88** handlers

## blueprint

| Handler | Description |
|---------|-------------|
| `blueprint.ac` | Verify one AC in §12. |
| `blueprint.block_for_architect` | Block for Architect manual review. |
| `blueprint.cancel` | Cancel a Blueprint. Governor-only. State → cancelled. |
| `blueprint.claim` | Executor claims the Blueprint. ready → in_progress + implicit executor assignment. |
| `blueprint.complete` | Declare execution complete. in_progress → done (completado + aprobado en 1 paso). |
| `blueprint.create` | Create a new Blueprint from BLP_TEMPLATE.md in draft state. |
| `blueprint.execute` | Execute a Blueprint: verify §3 preconditions, run §14 tasks sequentially, verify §12 ACs, mark complete (BLP-010 meta-handler). Supports dry_run mode. |
| `blueprint.fail` | Blueprint hit an obstacle. State → blocked. |
| `blueprint.list` | List Blueprints with optional filters. Paginated: limit + offset; fields total, returned, offset, next_offset report the pagination state. |
| `blueprint.re_delegate` | Re-delegate after verification failure. Re-opens a done/blocked blueprint. |
| `blueprint.read` | Read a full Blueprint (HCORTEX or CORTEX format). |
| `blueprint.ready` | Architect declares Blueprint ready for execution. draft → ready. |
| `blueprint.synthesize` | GUIDE MODE: creates or finds the BLP and returns the next pending section. Agent writes directly via blueprint.update(). synthesize does NOT write files. |
| `blueprint.task` | Update one task's checkbox in §14. Status: in_progress/completed. |
| `blueprint.update` | Update Blueprint progress with a note or refine a single section. |

## context

| Handler | Description |
|---------|-------------|
| `context.detect` | Scan upward from a path for a .arqux/ directory. Returns {found: bool, path: str|null, kind: 'project'|'workspace'|null}. |
| `context.full` | Return the full project context: project name, available cycles, current cycle, agents bound, skills available. |

## cortex

| Handler | Description |
|---------|-------------|
| `cortex.checkpoint` | Persist the agent's working state (WRK:current) as a single CORTEX line in brain.cortex §8. Accepts content as key:value pairs (fcs:,obj:,tasks:,state:). |
| `cortex.entry.add` | Add a new entry to a .cortex file. Accepts a 'content' CORTEX entry string (BLP-005, canal I) — when provided, fields extracted from content override individual params. Output metrics: bytes_written/entry_bytes = size of the serialized entry as written on disk (writer's form, quoting included); file_bytes = whole file size after the write. |
| `cortex.entry.delete` | Delete an entry matching a CORTEX selector from a .cortex file. Output metrics: bytes_written/file_bytes = whole file size after the rewrite (unlike entry.add, where bytes_written is the serialized entry size). |
| `cortex.entry.get` | Read entries matching a CORTEX selector from a .cortex file. format='cortex' returns raw CORTEX entries (canal I); format='hcortex' (default) returns parsed dicts (canal E). |
| `cortex.entry.list` | List entries in a .cortex file, optionally filtered. format='cortex' returns raw CORTEX entries (canal I); format='hcortex' (default) returns parsed dicts (canal E); format='compact' returns one raw entry per line. Paginated: limit (default 50) + offset; fields total, returned, offset, next_offset report the pagination state. |
| `cortex.entry.move` | Move an entry between sections in a .cortex file. Output metrics: bytes_written/file_bytes = whole file size after the rewrite (unlike entry.add, where bytes_written is the serialized entry size). |
| `cortex.entry.update` | Update an entry selected by a CORTEX selector. Output metrics: bytes_written/file_bytes = whole file size after the rewrite (unlike entry.add, where bytes_written is the serialized entry size). |
| `cortex.file.validate` | Scan a .cortex file for duplicate entry names and optionally fix them. |
| `cortex.format` | Transform content between CORTEX (machine) and HCORTEX (human-readable). target='hcortex' (default) renders sigils as readable headers; target='cortex' parses headers back. |
| `cortex.gc` | Garbage-collect or repair duplicate entries in a .cortex file. Duplicates share the same (section, sigil, name). Optional section/sigil/name filters restrict which duplicate groups are affected (all provided filters must match; unfiltered affects every duplicate group). keep='first' (default) conserves the first first_kept occurrences in file order; keep='last' conserves the last ones (metrics: retains the most recent values). mode='dedupe' (default) removes extra occurrences; mode='rename' preserves every occurrence and renames extras to the next sequential numeric id in the (section, sigil) namespace — global max numeric suffix + 1, incremented per rename (e.g. E_0157 extras -> E_0343, E_0344...); names without a numeric suffix get _001, _002... appended. Embedded event/id attrs are updated consistently (storage uses E_0157, API/event attr uses E-0157). dry_run=True (default) previews removals and the new names that would be assigned without mutating; force=True applies the mutation in a single atomic rewrite. Output metrics: bytes_written/file_bytes = whole file size after the rewrite (unlike entry.add, where bytes_written is the serialized entry size). |
| `cortex.learn` | Scan a project brain through the CODEC-CORTEX Learning Engine.
Returns scored entries and elevation candidates. |
| `cortex.learn.elevate` | Elevate a learning candidate (SES->LNG or LNG->KNW).
Default is dry-run (shows diff without applying).
Pass apply=true with confirm_hash from a reviewed dry-run to write the elevation to brain.cortex. |
| `cortex.migrate` | Migrate a .cortex file by applying a named transform (reseccionar|resigilar). Writes atomically (BLP-010 meta-handler). Supports dry_run mode. |
| `cortex.patch` | Patch multiple entries in a .cortex file from a CORTEX content payload (BLP-010 meta-handler). Accepts content as '$SELECTOR:{new_body}'. Supports dry_run mode. |
| `cortex.read` | Read and parse a .cortex file. mode='cortex' (default) returns raw CORTEX entries as dict (canal I); mode='hcortex' renders human-readable markdown (canal E). |
| `cortex.ref` | Return the definition of a CORTEX sigil (name, type, risk, layer, description). Reads from local sigil cache. sections=true returns the standard brain.cortex section map (section id → title → sigils) instead. |
| `cortex.render` | Render a .cortex file to HCORTEX READ markdown. |
| `cortex.render.diagram` | Render a PlantUML diagram to SVG/PNG. Requires plantuml.jar. |
| `cortex.render.validate_file` | Validate all PUML blocks in a file. Returns D1-D5 checklist. |
| `cortex.verify` | Verify a .cortex file's structure using CODEC-CORTEX. |
| `cortex.write` | Write (atomically) a .cortex file from CORTEX source text. Output metrics: bytes_written/file_bytes = whole file size written (the mutation is the full file). |

## cycle

| Handler | Description |
|---------|-------------|
| `cycle.close` | Close a cycle (no new tasks can be added). |
| `cycle.create` | Open a new cycle in the active project. |
| `cycle.current` | Get the currently active cycle. |
| `cycle.list` | List cycles in the active project. |
| `cycle.synthesize` | Populate a cycle's MANIFEST.md sections in a single call. |

## evidence

| Handler | Description |
|---------|-------------|
| `evidence.list` | Query the evidence trail. Paginated: limit (default 100) + offset; fields total, returned, offset, next_offset report the pagination state. |
| `evidence.read` | Read a single evidence event by ID. |
| `evidence.record` | Append an evidence entry to pulse.jsonl. |

## handler

| Handler | Description |
|---------|-------------|
| `handler.list` | Discover available handlers classified by module, filtered by tier (NANO|LITE|FULL). Paginated: limit (default 50) + offset; fields _total, _returned, _offset, _next_offset report the pagination state. compact=true returns names only. Replaces hardcoded handler tables in AGENTS.md (BLP-010 meta-handler). |

## identity

| Handler | Description |
|---------|-------------|
| `identity.get` | Return agent identity data from .arqux/identities/<agent>.cortex or the packaged identities. Default agent_id is 'alfred'. |
| `identity.record` | Record a behavioral lesson into the authenticated agent's identity file; explicit agent_id must match the caller (BLP-002). |

## project

| Handler | Description |
|---------|-------------|
| `project.bind` | Bind an agent identity to the current project with a role. |
| `project.init` | Initialize .arqux/ in a project directory and register it in the
workspace. |
| `project.lessons` | List lessons local to the current project. |
| `project.status` | Active project status (cycles, tasks, agents). |
| `project.unbind` | Release an agent binding from the current project. |

## protocol

| Handler | Description |
|---------|-------------|
| `protocol.adopt` | Onboard an agent with a role. |
| `protocol.onboard` | Onboard an agent with a role. Alias of protocol.adopt for w06 workflow compatibility. |
| `protocol.pause` | Suspend governance for the current session without losing state. |
| `protocol.release` | Fully detach an agent (clean exit, no orphans). |
| `protocol.resume` | Resume governance after a pause. |

## session

| Handler | Description |
|---------|-------------|
| `session.bootstrap` | Bootstrap a session using the authenticated identity. An explicit agent_id must match the caller (BLP-002). Returns cortex_context (canal I) and hcortex_dashboard (canal E). |
| `session.close` | Close the current session and write a portable SES entry to brain PULSE. |
| `session.context.get` | Read the current context pointer and return the formatted header. |
| `session.context.set` | Set the current session context pointer (project + scope + optional BLP). Validates project exists and returns the formatted header. |
| `session.handoff` | Serialize the current session context as CORTEX and write a handoff PULSE for the target agent (BLP-010 meta-handler). Supports dry_run mode. |
| `session.pulse.compact` | Compact pulse entries for a session. Prunes non-SES entries, writes consolidated LNG lesson. |
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
| `skill.edit` | Edit (read, write, or section-edit) a skill file in .arqux/skills/. Without content: returns the skill content. With content but no section: atomically replaces the entire skill file. With content and section: replaces only that CORTEX section (e.g. $0, $1, $2.1). Accepts content as CORTEX with keys name, body, section (BLP-009). |
| `skill.evolve` | Apply an approved adaptation to a skill. Default is dry-run. |
| `skill.import` | Acquire a skill from external source, store original in originals/. Accepts content as CORTEX with keys source, name, body (BLP-009). |
| `skill.install` | Install a skill: import + validate + register in brain.cortex $6/SKL (BLP-010 meta-handler). Supports dry_run mode. |
| `skill.list` | List all available skills in .arqux/skills/. |
| `skill.record` | Record a deviation (ADA) when a skill does not match the real context. |

## sync

| Handler | Description |
|---------|-------------|
| `sync.reconcile` | Reconcile brain.cortex with filesystem reality. Supports cycle-level (cycle_id) or project-level reconcile. |
| `sync.run` | Manually sync a project brain.cortex to meta-brain with full metrics. |

## task

| Handler | Description |
|---------|-------------|
| `task.claim` | An executor claims a task → status: in_progress. |
| `task.complete` | Mark a task done and record evidence. |
| `task.create` | Create a governed task in the current cycle. Accepts a 'content' CORTEX entry string (BLP-009) with keys obj, pre[], proc[], ac[], blk[], assignee, complexity, priority — parsed values override individual params (merge rule: content wins; scalar list values coerce to single-item lists). obj is optional when content carries an obj key; INVALID_ARGS otherwise. |
| `task.fail` | Mark a task blocked and record the cause. |
| `task.list` | List tasks with filters. Paginated: limit + offset; fields total, returned, offset, next_offset report the pagination state. |
| `task.read` | Read a task (CORTEX or HCORTEX format). |
| `task.run` | Run a governed task: verify preconditions, execute procedure steps, mark complete or fail (BLP-010 meta-handler). Supports dry_run mode. |
| `task.update` | Update task progress, optionally change status. |

## workspace

| Handler | Description |
|---------|-------------|
| `workspace.init` | Initialize .arqux/ at the workspace root. |
| `workspace.lessons` | List lessons elevated to the meta-brain. |
| `workspace.status` | Workspace status (OUT-MIN by default). Use --dashboard for rich output. |

