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

$2.1: WORKSPACE EXAMPLES

STP:init_new{ example:"workspace.init(path='/home/user/my-workspace')", result:"Creates .arqux/ + AGENTS.md + identities/ + skills/ at the specified path", note:"Si no se provee path, usa el directorio actual. Siempre pasar path para evitar ambigüedad." }
STP:check_status{ example:"workspace.status()", result:"OUT-MIN governor=alfred manifest=yes projects=1" }
STP:check_verbose{ example:"workspace.status(verbose=true)", result:"Detalle completo: proyectos registrados, version del manifest, governor" }


$3: PROJECT (5 handlers)

HDL:project.init{ signature:"init(name, path?, seed?)", purpose:"Initialize .arqux/ in a project. seed= pre-populates brain.cortex in one step. This is the ONLY entry point for project governance." }
HDL:project.bind{ signature:"bind(agent_id, role, path?)", purpose:"Bind agent to project (writes to brain SESSIONS)" }
HDL:project.unbind{ signature:"unbind(agent_id, path?)", purpose:"Release agent binding (marks session as released)" }
HDL:project.status{ signature:"status(path?)", purpose:"Active project status (cycles, tasks, agents, brain_version)" }
HDL:project.lessons{ signature:"lessons(path?)", purpose:"List lessons from brain LESSONS section (contextual, this project only)" }

$3.1: PROJECT EXAMPLES

STP:init_with_seed{ example:"project.init(name='mi-proyecto', path='./mi-proyecto', seed=contenido_cortex)", result:".arqux/ + brain poblado + registro en workspace + meta-brain actualizado", note:"El seed lo prepara el agente LLM tras estudiar el proyecto. Sin seed: project.init emite STP:build_brain con instrucciones." }
STP:init_no_seed{ example:"project.init(name='mi-proyecto', path='./mi-proyecto')", result:".arqux/ creado con brain esqueleto + instrucciones STP:build_brain", pitfall:"No olvides leer las instrucciones STP y llamar project.init devuelta con seed." }
STP:bind_agent{ example:"project.bind(agent_id='alfred', role='governor', path='./mi-proyecto')", result:"SES:alfred en brain SESSIONS + brain_version incrementado", note:"roles validos: governor, executor, auditor." }
STP:unbind_agent{ example:"project.unbind(agent_id='alfred', path='./mi-proyecto')", result:"SES marcado como released en SESSIONS", note:"La sesion se conserva para historial. No se elimina." }
STP:check_project{ example:"project.status(path='./mi-proyecto')", result:"OUT-WORK cycles=2 active_agents=1 brain_version=3 project=mi-proyecto" }


$4: CYCLE (4 handlers)

HDL:cycle.create{ signature:"create(name?, description?, path?)", purpose:"Open a new cycle" }
HDL:cycle.list{ signature:"list(status?, path?)", purpose:"List cycles, optionally filtered by open/closed" }
HDL:cycle.current{ signature:"current(path?)", purpose:"Get the currently active cycle" }
HDL:cycle.close{ signature:"close(cycle_id, summary?, path?)", purpose:"Close a cycle (no new tasks)" }

$4.1: CYCLE EXAMPLES

STP:create{ example:"cycle.create(name='CYCLE-02', description='Feature: refactor state.py', path='./mi-proyecto')", result:"Nuevo ciclo creado en .arqux/cycles/CYCLE-02/", note:"El nombre es libre pero se recomienda CYCLE-NN para mantener consistencia." }
STP:close{ example:"cycle.close(cycle_id='CYCLE-02', summary='Refactor completado. state.py partido en 3 modulos.', path='./mi-proyecto')", result:"Ciclo cerrado, no se pueden agregar nuevas tareas", note:"El summary queda registrado en el ciclo para referencia futura." }


$5: TASK (7 handlers)

HDL:task.create{ signature:"create(obj, pre?, proc?, ac?, blk?, assignee?, complexity?, priority?, path?)", purpose:"Create governed task" }
HDL:task.claim{ signature:"claim(task_id, path?)", purpose:"Executor claims task -> in_progress" }
HDL:task.update{ signature:"update(task_id, note, status?, path?)", purpose:"Update task progress" }
HDL:task.complete{ signature:"complete(task_id, evidence?, path?)", purpose:"Mark task done, record evidence" }
HDL:task.fail{ signature:"fail(task_id, reason?, path?)", purpose:"Mark task blocked, record cause" }
HDL:task.read{ signature:"read(task_id, format?, path?)", purpose:"Read task (cortex or hcortex)" }
HDL:task.list{ signature:"list(status?, assignee?, cycle?, path?)", purpose:"List tasks with filters" }

$5.1: TASK EXAMPLES

STP:create_simple{ example:"task.create(obj='Implementar handler X', assignee='alfred', path='./mi-proyecto')", result:"T-001 creada en ciclo activo con status=draft", note:"obj es el unico campo requerido. El resto son opcionales." }
STP:create_full{ example:"task.create(obj='Refactor state.py', pre=['Leer codigo actual','Planificar division'], proc=['Crear pulse.py','Crear sessions.py','Actualizar imports'], ac=['57 tests pasan','No regresion'], assignee='alfred', complexity='complex', path='./mi-proyecto')", result:"T-002 con precondiciones, procedimiento, criterios de aceptacion y asignacion" }
STP:claim{ example:"task.claim(task_id='T-002', path='./mi-proyecto')", result:"T-002 status=in_progress", pitfall:"Solo executor puede claim. Governor NO puede claim tasks." }
STP:update_progress{ example:"task.update(task_id='T-002', note='pulse.py creado. Trabajando en sessions.py.', path='./mi-proyecto')", result:"Nota registrada, status sin cambios", note:"Usar status='in_progress' o status='blocked' si se necesita cambiar el estado." }
STP:complete{ example:"task.complete(task_id='T-002', evidence='57 tests passing. No regresion detectada.', path='./mi-proyecto')", result:"T-002 status=done + AUD en brain PULSE", note:"La evidencia queda registrada automaticamente en el brain." }
STP:fail{ example:"task.fail(task_id='T-002', reason='Dependencia externa no disponible. Bloqueado hasta Q2.', path='./mi-proyecto')", result:"T-002 status=blocked + AUD en brain PULSE con la causa" }


$6: EVIDENCE (3 handlers)

HDL:evidence.record{ signature:"record(task_id, kind, payload, path?)", purpose:"Append evidence to brain PULSE" }
HDL:evidence.list{ signature:"list(task_id?, cycle?, since?, limit?, path?)", purpose:"Query evidence trail" }
HDL:evidence.read{ signature:"read(event_id, path?)", purpose:"Read single evidence event by ID" }

$6.1: EVIDENCE EXAMPLES

STP:record{ example:"evidence.record(task_id='T-002', kind='artifact', payload='state.py refactor: 57 tests passing', path='./mi-proyecto')", result:"AUD:E_0002 en brain PULSE", note:"kind valido: note, artifact, decision, metric, blocker." }
STP:list_recent{ example:"evidence.list(task_id='T-002', limit=5, path='./mi-proyecto')", result:"Lista los ultimos 5 eventos de la tarea T-002", note:"Sin filtros, lista hasta 100 eventos del proyecto." }
STP:read_event{ example:"evidence.read(event_id='E_0002', path='./mi-proyecto')", result:"Detalle completo del evento con ts, task, kind, agent, payload" }


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
