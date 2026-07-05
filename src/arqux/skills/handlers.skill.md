$0

# -- $0: HANDLERS SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Actor / workspace identity
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler definition
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable principle


$1: SURFACE

IDN:surface{ total:30, governance:24, utility:4, identity:1, protocol:2 (pause/resume counted as session-only) }

AXM:handlers_only{ Governance state is mutated exclusively via MCP handlers. No direct file editing of .cortex governance files. The handler is the interface. The file is the storage. }


$2: WORKSPACE (3 handlers)

HDL:workspace.init{ signature:"init(path?)", purpose:"Initialize .arqux/ at workspace root" }
HDL:workspace.status{ signature:"status(verbose?, path?)", purpose:"Workspace status (OUT-MIN by default)" }
HDL:workspace.lessons{ signature:"lessons(project?, path?)", purpose:"List lessons elevated to the meta-brain" }


$3: PROJECT (5 handlers)

HDL:project.init{ signature:"init(name, path?, seed?)", purpose:"Initialize .arqux/ in a project. seed= pre-populates brain.cortex in one step. This is the ONLY entry point for project governance." }
HDL:project.bind{ signature:"bind(agent_id, role, path?)", purpose:"Bind agent to project (writes to brain SESSIONS)" }
HDL:project.unbind{ signature:"unbind(agent_id, path?)", purpose:"Release agent binding (marks session as released)" }
HDL:project.status{ signature:"status(path?)", purpose:"Active project status (cycles, tasks, agents, brain_version)" }
HDL:project.lessons{ signature:"lessons(path?)", purpose:"List lessons from brain LESSONS section (contextual, this project only)" }


$4: CYCLE (4 handlers)

HDL:cycle.create{ signature:"create(name?, description?, path?)", purpose:"Open a new cycle" }
HDL:cycle.list{ signature:"list(status?, path?)", purpose:"List cycles, optionally filtered by open/closed" }
HDL:cycle.current{ signature:"current(path?)", purpose:"Get the currently active cycle" }
HDL:cycle.close{ signature:"close(cycle_id, summary?, path?)", purpose:"Close a cycle (no new tasks)" }


$5: TASK (7 handlers)

HDL:task.create{ signature:"create(obj, pre?, proc?, ac?, blk?, assignee?, complexity?, priority?, path?)", purpose:"Create governed task" }
HDL:task.claim{ signature:"claim(task_id, path?)", purpose:"Executor claims task -> in_progress" }
HDL:task.update{ signature:"update(task_id, note, status?, path?)", purpose:"Update task progress" }
HDL:task.complete{ signature:"complete(task_id, evidence?, path?)", purpose:"Mark task done, record evidence" }
HDL:task.fail{ signature:"fail(task_id, reason?, path?)", purpose:"Mark task blocked, record cause" }
HDL:task.read{ signature:"read(task_id, format?, path?)", purpose:"Read task (cortex or hcortex)" }
HDL:task.list{ signature:"list(status?, assignee?, cycle?, path?)", purpose:"List tasks with filters" }


$6: EVIDENCE (3 handlers)

HDL:evidence.record{ signature:"record(task_id, kind, payload, path?)", purpose:"Append evidence to brain PULSE" }
HDL:evidence.list{ signature:"list(task_id?, cycle?, since?, limit?, path?)", purpose:"Query evidence trail" }
HDL:evidence.read{ signature:"read(event_id, path?)", purpose:"Read single evidence event by ID" }


$7: PROTOCOL (4 handlers)

HDL:protocol.adopt{ signature:"adopt(agent_id, role, path?)", purpose:"Onboard agent with a role" }
HDL:protocol.release{ signature:"release(agent_id, path?)", purpose:"Fully detach agent (clean exit)" }
HDL:protocol.pause{ signature:"pause()", purpose:"Suspend governance without losing state" }
HDL:protocol.resume{ signature:"resume()", purpose:"Resume governance after pause" }


$8: CORTEX UTILITY (4 handlers)

HDL:cortex.read{ signature:"read(path)", purpose:"Read and parse a .cortex file" }
HDL:cortex.write{ signature:"write(path, content, force?)", purpose:"Write a .cortex file (not for governance files)" }
HDL:cortex.verify{ signature:"verify(path)", purpose:"Validate .cortex file structure" }
HDL:cortex.render{ signature:"render(path)", purpose:"Render .cortex to HCORTEX READ markdown" }


$9: IDENTITY (1 handler)

HDL:identity.record{ signature:"record(lesson, kind?, cause?, agent_id?, path?)", purpose:"Record behavioral lesson into agent's identity file. This evolves the agent's identity with each significant lesson." }
