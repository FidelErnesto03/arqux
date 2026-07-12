# ArqUX Handlers

Total: **73** handlers

## blueprint

| Handler | Description |
|---------|-------------|
| `blueprint.ac` | Verify one AC in §12. Fail triggers auto re-delegate (max 3). |
| `blueprint.approve` | Auditor approves after cross-verification. State → done. |
| `blueprint.assign` | Governor assigns an executor to the Blueprint. |
| `blueprint.block_for_architect` | Block for Architect manual review after 3rd verification fail. |
| `blueprint.cancel` | Cancel a Blueprint. Governor-only. State → cancelled. |
| `blueprint.claim` | Executor claims the Blueprint. State → in_progress. |
| `blueprint.complete` | Declare execution complete. State → review. |
| `blueprint.create` | Create a new Blueprint from BLP_TEMPLATE.md in draft state. |
| `blueprint.define` | Fill the Blueprint's definition sections. State → defined. |
| `blueprint.fail` | Blueprint hit an obstacle. State → blocked. |
| `blueprint.gate` | Approve one or all Blueprint quality gates after Architect maturation. |
| `blueprint.list` | List Blueprints with optional filters. |
| `blueprint.mature` | Enter maturation phase. Mode 'live' for synchronous co-design, 'async' (default) for cyclic iteration. |
| `blueprint.re_delegate` | Re-delegate after verification fail (max 3 loops). |
| `blueprint.read` | Read a full Blueprint (HCORTEX or CORTEX format). |
| `blueprint.ready` | Architect declares Blueprint ready for execution. |
| `blueprint.task` | Update one task's checkbox in §14. Status: in_progress/completed. |
| `blueprint.update` | Update Blueprint progress with a note or refine a single section. |

## cortex

| Handler | Description |
|---------|-------------|
| `cortex.entry.add` | Add a new entry to a .cortex file. |
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
workspace. |
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

## workspace

| Handler | Description |
|---------|-------------|
| `workspace.init` | Initialize .arqux/ at the workspace root. |
| `workspace.lessons` | List lessons elevated to the meta-brain. |
| `workspace.status` | Workspace status (OUT-MIN by default). |

