$0

# -- $0: HANDLERS SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Actor / workspace identity
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler definition
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable principle


$1: SURFACE

IDN:surface{ total:62, governance:39, utility:16, blueprint:18, skill:5, session:3 }

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


$8: CORTEX UTILITY (7 handlers)

HDL:cortex.read{ signature:"read(path)", purpose:"Read and parse a .cortex file" }
HDL:cortex.write{ signature:"write(path, content, force?)", purpose:"Write a .cortex file (not for governance files)" }
HDL:cortex.verify{ signature:"verify(path)", purpose:"Validate .cortex file structure" }
HDL:cortex.render{ signature:"render(path)", purpose:"Render .cortex to HCORTEX READ markdown" }
HDL:cortex.render.validate_file{ signature:"validate_file(path)", purpose:"Validate all PUML blocks in a file. Returns D1-D5 checklist." }
HDL:cortex.render.diagram{ signature:"render(diagram_source, format?, path?)", purpose:"Render a PlantUML diagram to SVG/PNG" }
HDL:setup.plantuml{ signature:"plantuml(force?, path?)", purpose:"Download and install plantuml.jar to ~/.arqux/bin/" }

$8.1: CORTEX LEARNING (2 handlers)

HDL:cortex.learn{ signature:"learn(scope?, path?)", purpose:"Scan a project brain through the learning engine. Returns scored entries and elevation candidates." }
HDL:cortex.learn.elevate{ signature:"elevate(candidate_id, apply?, confirm_hash?, path?)", purpose:"Elevate a learning candidate (SES->LNG or LNG->KNW). Default is dry-run." }


$9: IDENTITY (1 handler)

HDL:identity.record{ signature:"record(lesson, kind?, cause?, agent_id?, path?)", purpose:"Record behavioral lesson into agent's identity file. This evolves the agent's identity with each significant lesson." }


$10: SESSION (3 handlers)

HDL:session.close{ signature:"close(path?)", purpose:"End the current session. Saves SES handoff to brain PULSE." }
HDL:session.resume{ signature:"resume(path?)", purpose:"Resume a previous session from stored SES context in brain PULSE." }
HDL:session.status{ signature:"status(path?)", purpose:"Get the current session status (active SES, bound agent, project)." }


$11: SKILL (5 handlers)

HDL:skill.list{ signature:"list(path?)", purpose:"List all available skills in .arqux/skills/" }
HDL:skill.import{ signature:"import(source, name, content?, path?)", purpose:"Acquire a skill from external source. Stores original in originals/." }
HDL:skill.record{ signature:"record(name, expected, actual, reason, path?)", purpose:"Record a deviation (ADA) when a skill does not match real context." }
HDL:skill.evolve{ signature:"evolve(name, adaptation_id, apply?, path?)", purpose:"Apply an approved adaptation to a skill. Default is dry-run." }
HDL:skill.convert{ signature:"convert(name, path?)", purpose:"Convert a skill from original format to CORTEX ultra-dense format." }


$12: BLUEPRINT (18 handlers)

HDL:blueprint.create{ signature:"create(obj, cycle?, path?)", purpose:"Create a new Blueprint from BLP_TEMPLATE.md in draft state" }
HDL:blueprint.define{ signature:"define(bp_id, pre?, scope?, exclusions?, mandatory_rules?, acceptance_criteria?, procedure?, validations?, technical_design?, operational_design?, risks?, blocking_rule?, path?)", purpose:"Fill Blueprint definition sections. State → defined" }
HDL:blueprint.mature{ signature:"mature(bp_id, mode?, path?)", purpose:"Enter maturation phase. mode='async' (default) for cyclic iteration, mode='live' for synchronous co-design" }
HDL:blueprint.gate{ signature:"gate(bp_id, gate?, path?)", purpose:"Approve one or all Blueprint quality gates after Architect maturation" }
HDL:blueprint.ready{ signature:"ready(bp_id, path?)", purpose:"Architect declares Blueprint ready. State → ready" }
HDL:blueprint.assign{ signature:"assign(bp_id, executor, path?)", purpose:"Governor assigns executor to Blueprint" }
HDL:blueprint.claim{ signature:"claim(bp_id, path?)", purpose:"Executor claims Blueprint. State → in_progress" }
HDL:blueprint.task{ signature:"task(bp_id, task_id, status, evidence?, path?)", purpose:"Update one task's checkbox in §14. status: in_progress/completed" }
HDL:blueprint.ac{ signature:"ac(bp_id, ac_id, status, evidence?, reason?, path?)", purpose:"Verify one AC in §12. Fail triggers auto re-delegate (max 3)" }
HDL:blueprint.update{ signature:"update(bp_id, note?, section?, content?, puml?, path?)", purpose:"Update Blueprint progress (note) or refine a single section" }
HDL:blueprint.complete{ signature:"complete(bp_id, evidence?, path?)", purpose:"Declare execution complete. State → review" }
HDL:blueprint.fail{ signature:"fail(bp_id, reason?, path?)", purpose:"Blueprint hit an obstacle. State → blocked" }
HDL:blueprint.approve{ signature:"approve(bp_id, path?)", purpose:"Auditor approves after cross-verification. State → done" }
HDL:blueprint.cancel{ signature:"cancel(bp_id, reason?, path?)", purpose:"Cancel a Blueprint. Governor-only. State → cancelled" }
HDL:blueprint.re_delegate{ signature:"re_delegate(bp_id, path?)", purpose:"Re-delegate after verification fail (max 3 loops)" }
HDL:blueprint.block_for_architect{ signature:"block_for_architect(bp_id, path?)", purpose:"Block for Architect manual review after 3rd verification fail" }
HDL:blueprint.read{ signature:"read(bp_id, format?, path?)", purpose:"Read full Blueprint (HCORTEX or CORTEX)" }
HDL:blueprint.list{ signature:"list(cycle?, status?, path?)", purpose:"List Blueprints with optional filters" }

$12.1: BLUEPRINT EXAMPLES

STP:create{ example:"blueprint.create(obj='Implement OAuth2', cycle='CYCLE-01', path='./proyecto')", result:"BLP-003 creado en draft con contexto pre-poblado" }
STP:task_update{ example:"blueprint.task(bp_id='BLP-001', task_id='T-1.1', status='completed', evidence='Handler implementado y testeado', path='./proyecto')", result:"Checkbox T-1.1 marcado como [x] con evidencia" }
STP:ac_verify{ example:"blueprint.ac(bp_id='BLP-001', ac_id='AC-01', status='verified', evidence='Tests pasan', path='./proyecto')", result:"AC-01 marcado como [x]. exit_code=0." }
STP:ac_fail{ example:"blueprint.ac(bp_id='BLP-001', ac_id='AC-03', status='failed', reason='No cumple criterio', path='./proyecto')", result:"Dispara re_delegate automatico. Loop count incrementado." }
STP:section_update{ example:"blueprint.update(bp_id='BLP-002', section='§3', content='## §3: Preconditions\\n\\n- [ ] Precond 1', path='./proyecto')", result:"Solo §3 reemplazado. Otras secciones intactas." }
