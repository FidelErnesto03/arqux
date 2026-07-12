# handlers-catalogo.hcortex.md
> Catalogo de referencia: los 73 MCP handlers de ArqUX
> Fuente: arqux.handlers.REGISTRY + arqux/skills/mcp-handlers.skill.md
> Generado: 2026-07-12
> Idioma: espanol

---

$0: METADATA
IDN:handlers_catalog{ name:"ArqUX MCP Handlers Catalog", total:74, modules:12, source:"mcp-handlers.skill.md $6", activos:64, deprecados:10, nuevos:1 }
WRK:catalog{ status:"reference", mapped_to_workflows:34, not_mapped:30 }

---

# 1. COMO LEER ESTE CATALOGO

Cada handler es una funcion registrada en `arqux.handlers.REGISTRY` (la unica fuente de
verdad). Se exponen como herramientas MCP; los puntos (`.`) del nombre se convierten en
guiones bajos (`_`) en el cable (p.ej. `cortex.read` -> `cortex_read`).

**Clasificacion por categoria** (segun `AXM:governance_vs_utility`):
- **Gobernanza**: mutan el estado de ArqUX (workspace, project, cycle, task, evidence,
  protocol, session, blueprint, skill, identity).
- **Utilidad**: leen / inspeccionan / renderizan sin side-effects (`cortex.*`, `setup.*`).

**Cobertura por workflow**: 42 de 73 handlers aparecen en los diagramas de los 11
workflows canonicos; 31 son operaciones atomicas de soporte (utilidad + ciclo de vida
secundario) que los agentes invocan ad-hoc. No estan en los diagramas por diseno, no por
falta de uso (ver `AXM:fixed_budget`: el surface tiene presupuesto fijo).

**Columnas por handler**: nombre REGISTRY | tool MCP | categoria | en workflow | firma |
para que / cuando usarlo.

# 2. RESUMEN POR CATEGORIA

- **Gobernanza**: 57 handlers (mutan estado).
- **Utilidad**: 16 handlers (lectura/render, sin side-effects).
- **En workflows**: 42 | **Fuera de workflows**: 31.

# 3. CATALOGO POR MODULO

## Modulo `workspace` (3 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| workspace.init | workspace_init | Gobernanza | w01 | `init(path?)` | Initialize .arqux/ at the workspace root. Parte del flujo canonico w01. Paso de gobernanza del workflow. |
| workspace.lessons | workspace_lessons | Gobernanza | — | `lessons(project?, path?)` | List lessons elevated to the meta-brain. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| workspace.status | workspace_status | Gobernanza | — | `status(verbose?, path?)` | Workspace status (OUT-MIN by default). Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |

## Modulo `project` (5 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| project.bind | project_bind | Gobernanza | — | `bind(agent_id, role, path?)` | Bind an agent identity to the current project with a role. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| project.init | project_init | Gobernanza | w02 | `init(name, path?, seed?)` | Initialize .arqux/ in a project directory and register it in the workspace. Parte del flujo canonico w02. Paso de gobernanza del workflow. |
| project.lessons | project_lessons | Gobernanza | — | `lessons(path?)` | List lessons local to the current project. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| project.status | project_status | Gobernanza | — | `status(path?)` | Active project status (cycles, tasks, agents). Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| project.unbind | project_unbind | Gobernanza | — | `unbind(agent_id, path?)` | Release an agent binding from the current project. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |

## Modulo `cycle` (5 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| cycle.close | cycle_close | Gobernanza | w08 | `close(cycle_id, summary, path?)` | Close a cycle (no new tasks can be added). Parte del flujo canonico w08. Paso de gobernanza del workflow. |
| cycle.create | cycle_create | Gobernanza | — | `create(name, description, path?)` | Open a new cycle in the active project. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| cycle.current | cycle_current | Gobernanza | — | `current(path?)` | Get the currently active cycle. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| cycle.list | cycle_list | Gobernanza | — | `list(status?, path?)` | List cycles in the active project. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| cycle.mature | cycle_mature | Gobernanza | — | `mature(cycle_id, path?)` | Mature a cycle (draft to ready). Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |

## Modulo `task` (7 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| task.claim | task_claim | Gobernanza | w04 | `claim(task_id, path?)` | An executor claims a task → status: in_progress. Parte del flujo canonico w04. Paso de gobernanza del workflow. |
| task.complete | task_complete | Gobernanza | w04 | `complete(task_id, evidence, path?)` | Mark a task done and record evidence. Parte del flujo canonico w04. Paso de gobernanza del workflow. |
| task.create | task_create | Gobernanza | w04 | `create(obj, pre?, proc?, ac?, blk?, assignee?, complexity?, priority?, path?)` | Create a governed task in the current cycle. Parte del flujo canonico w04. Paso de gobernanza del workflow. |
| task.fail | task_fail | Gobernanza | — | `fail(task_id, reason, path?)` | Mark a task blocked and record the cause. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| task.list | task_list | Gobernanza | — | `list(status?, assignee?, cycle?, path?)` | List tasks with filters. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| task.read | task_read | Gobernanza | — | `read(task_id, format?, path?)` | Read a task (CORTEX or HCORTEX format). Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| task.update | task_update | Gobernanza | w04 | `update(task_id, note, status?, path?)` | Update task progress, optionally change status. Parte del flujo canonico w04. Paso de gobernanza del workflow. |

## Modulo `evidence` (3 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| evidence.list | evidence_list | Gobernanza | — | `list(task_id?, cycle?, since?, limit?, path?)` | Query the evidence trail. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| evidence.read | evidence_read | Gobernanza | — | `read(event_id, path?)` | Read a single evidence event by ID. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| evidence.record | evidence_record | Gobernanza | w04/w10 | `record(task_id, kind, payload, path?)` | Append an evidence entry to pulse.jsonl. Parte del flujo canonico w04/w10. Paso de gobernanza del workflow. |

## Modulo `protocol` (4 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| protocol.adopt | protocol_adopt | Gobernanza | w06 | `adopt(agent_id, role, path?)` | Onboard an agent with a role. Parte del flujo canonico w06. Paso de gobernanza del workflow. |
| protocol.pause | protocol_pause | Gobernanza | — | `pause()` | Suspend governance for the current session without losing state. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| protocol.release | protocol_release | Gobernanza | — | `release(agent_id, path?)` | Fully detach an agent (clean exit, no orphans). Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| protocol.resume | protocol_resume | Gobernanza | — | `resume()` | Resume governance after a pause. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |

## Modulo `session` (5 handlers → 6 con context.full)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| session.close | session_close | Gobernanza | — | `close(summary, blps?, tasks?, decisions?, gaps?, path?)` | Close session and write portable SES entry to brain PULSE. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| session.context.get | session_context_get | Gobernanza | w03 | `context.get(path?)` | Read the current context pointer and return formatted header. Parte del flujo canonico w03. Paso de gobernanza del workflow. |
| session.context.set | session_context_set | Gobernanza | w10 | `context.set(project, scope, blp?, path?)` | Set the current session context pointer. Validates project exists. Parte del flujo canonico w10. Paso de gobernanza del workflow. |
| **context.full** (NUEVO) | context_full | Gobernanza | w08 | `full(project, scope, path?)` | **NUEVO — paso 3 del w08 conversacional.** Agrupa project.status + cycle.current + cycle.list en 1 respuesta de contexto completo. |
| session.resume | session_resume | Gobernanza | w08 | `resume(path?)` | Read last SES entry from brain PULSE and restore the context. Parte del flujo canonico w08. Paso de gobernanza del workflow. |
| session.status | session_status | Gobernanza | — | `status(path?)` | Read SES metadata without restoring full context. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |

## Modulo `cortex` (15 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| cortex.entry.add | cortex_entry_add | Utilidad | w11 | `entry.add(path, section, sigil, name, value, create_section?, force?)` | Add a new entry to a .cortex file. Parte del flujo canonico w11. |
| cortex.entry.delete | cortex_entry_delete | Utilidad | — | `entry.delete(path, selector, force?)` | Delete an entry matching a CORTEX selector. Inspeccion/render bajo demanda, sin side-effects. Se invoca ad-hoc (no es paso de un workflow). |
| cortex.entry.get | cortex_entry_get | Utilidad | — | `entry.get(path, selector)` | Read entries matching a CORTEX selector. Inspeccion/render bajo demanda, sin side-effects. Se invoca ad-hoc (no es paso de un workflow). |
| cortex.entry.list | cortex_entry_list | Utilidad | — | `entry.list(path, section?, sigil?)` | List entries in a .cortex file, optionally filtered. Inspeccion/render bajo demanda, sin side-effects. Se invoca ad-hoc (no es paso de un workflow). |
| cortex.entry.move | cortex_entry_move | Utilidad | — | `entry.move(path, selector, to_section)` | Move an entry between sections. Inspeccion/render bajo demanda, sin side-effects. Se invoca ad-hoc (no es paso de un workflow). |
| cortex.entry.update | cortex_entry_update | Utilidad | w09 | `entry.update(path, selector, set_?, replace_body?, append?, force?)` | Update an entry selected by a CORTEX selector. Parte del flujo canonico w09. |
| cortex.file.validate | cortex_file_validate | Utilidad | w09 | `file.validate(path, fix?)` | Scan a .cortex file for duplicate entry names and optionally fix them. Parte del flujo canonico w09. |
| cortex.learn | cortex_learn | Utilidad | w08 | `learn(scope?, path?)` | Scan a project brain through the Learning Engine. Returns scored entries. Parte del flujo canonico w08. |
| cortex.learn.elevate | cortex_learn_elevate | Utilidad | w08 | `learn.elevate(candidate_id, apply?, confirm_hash?, path?)` | Elevate a learning candidate (SES→LNG or LNG→KNW). Parte del flujo canonico w08. |
| cortex.read | cortex_read | Utilidad | w03/w06/w10/w11 | `read(path)` | Read and parse a .cortex file using CODEC-CORTEX. Parte del flujo canonico w03/w06/w10/w11. |
| cortex.render | cortex_render | Utilidad | — | `render(path)` | Render a .cortex file to HCORTEX READ markdown. Inspeccion/render bajo demanda, sin side-effects. Se invoca ad-hoc (no es paso de un workflow). |
| cortex.render.diagram | cortex_render_diagram | Utilidad | — | `render.diagram(source, format?, path?)` | Render a PlantUML diagram to SVG/PNG. Inspeccion/render bajo demanda, sin side-effects. Se invoca ad-hoc (no es paso de un workflow). |
| cortex.render.validate_file | cortex_render_validate_file | Utilidad | — | `render.validate_file(path)` | Validate all PUML blocks in a file (D1-D5 checklist). Inspeccion/render bajo demanda, sin side-effects. Se invoca ad-hoc (no es paso de un workflow). |
| cortex.verify | cortex_verify | Utilidad | w09/w11 | `verify(path)` | Verify a .cortex file's structure using CODEC-CORTEX. Parte del flujo canonico w09/w11. |
| cortex.write | cortex_write | Utilidad | w11 | `write(path, content, force?)` | Write (atomically) a .cortex file from CORTEX source text. Parte del flujo canonico w11. |

## Modulo `identity` (1 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| identity.record | identity_record | Gobernanza | w04/w05/w11 | `record(lesson, kind?, cause?, agent_id?, path?)` | Record a behavioral lesson into the agent's identity file. Parte del flujo canonico w04/w05/w11. Paso de gobernanza del workflow. |

## Modulo `blueprint` (18 handlers → 9 activos + 1 nuevo + 8 deprecados)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| ~~blueprint.ac~~ | ~~blueprint_ac~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`ac(bp_id, ac_id, status, evidence?, reason?, path?)`~~ | ~~Verify one AC in §12.~~ **DEPRECATED — w08 conversacional: los ACs se definen y verifican durante la conversacion, no hay loop de ACs post-aprobacion.** |
| ~~blueprint.approve~~ | ~~blueprint_approve~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`approve(bp_id, path?)`~~ | ~~Auditor approves after cross-verification.~~ **DEPRECATED — w08 conversacional: el Arquitecto aprueba verbalmente ("ok"), no hay handler de approve.** |
| ~~blueprint.assign~~ | ~~blueprint_assign~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`assign(bp_id, executor, path?)`~~ | ~~Governor assigns an executor.~~ **DEPRECATED — w08 conversacional: quien ejecuta se define durante la conversacion, no hay assign formal.** |
| ~~blueprint.block_for_architect~~ | ~~blueprint_block_for_architect~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`block_for_architect(bp_id, path?)`~~ | ~~Block for Architect manual review after 3rd verification fail.~~ **DEPRECATED — w08 conversacional: el Arquitecto ya esta en la conversacion, no necesita block-for-architect.** |
| blueprint.cancel | blueprint_cancel | Gobernanza | w08 | `cancel(bp_id, reason, path?)` | Cancel a Blueprint. Governor-only. State → cancelled. Se conserva para casos de cancelacion explicita. |
| ~~blueprint.claim~~ | ~~blueprint_claim~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`claim(bp_id, path?)`~~ | ~~Executor claims the Blueprint.~~ **DEPRECATED — w08 conversacional: el agente que conversa es el ejecutor, no hay claim separado.** |
| blueprint.complete | blueprint_complete | Gobernanza | w08 | `complete(bp_id, evidence, path?)` | Declare execution complete. State → review. Se conserva para marcar fin de ejecucion. |
| ~~blueprint.create~~ | ~~blueprint_create~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`create(obj, cycle?, path?)`~~ | ~~Create a new Blueprint from BLP_TEMPLATE.md.~~ **DEPRECATED — w08 conversacional: `blueprint.synthesize` crea + llena en 1 paso.** |
| blueprint.define | blueprint_define | Gobernanza | — | `define(bp_id, pre?, scope?, exclusions?, acceptance_criteria?, procedure?, validations?, technical_design?, operational_design?, risks?, blocking_rule?, path?)` | Fill the Blueprint's definition sections. State → defined. Operacion de ciclo de vida secundaria. Se conserva para casos excepcionales (edicion manual fuera del flujo conversacional). |
| blueprint.fail | blueprint_fail | Gobernanza | w08 | `fail(bp_id, reason, path?)` | Blueprint hit an obstacle. State → blocked. Se conserva para bloqueos imprevistos. |
| ~~blueprint.gate~~ | ~~blueprint_gate~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`gate(bp_id, gate?, path?)`~~ | ~~Approve quality gates after maturation.~~ **DEPRECATED — w08 conversacional: las compuertas se verifican durante la conversacion, no hay gates intermedios.** |
| blueprint.list | blueprint_list | Gobernanza | — | `list(cycle?, status?, path?)` | List Blueprints with optional filters. Se conserva para consulta ad-hoc. |
| ~~blueprint.mature~~ | ~~blueprint_mature~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`mature(bp_id, mode?, path?)`~~ | ~~Enter maturation phase.~~ **DEPRECATED — w08 conversacional: la maduracion es la conversacion misma, no hay handler de mature.** |
| blueprint.read | blueprint_read | Gobernanza | w08 | `read(bp_id, format?, path?)` | Read a full Blueprint (HCORTEX or CORTEX format). Se conserva para lectura de BLPs. |
| blueprint.ready | blueprint_ready | Gobernanza | w08 | `ready(bp_id, path?)` | Architect declares Blueprint ready for execution. Se conserva para transicion formal a ejecucion. |
| ~~blueprint.re_delegate~~ | ~~blueprint_re_delegate~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`re_delegate(bp_id, path?)`~~ | ~~Re-delegate after verification fail.~~ **DEPRECATED — w08 conversacional: no hay fallo de AC post-aprobacion, no aplica re-delegate.** |
| blueprint.task | blueprint_task | Gobernanza | w08 | `task(bp_id, task_id, status, evidence?, path?)` | Update one task's checkbox in §14. Se conserva para checkpoint durante ejecucion. |
| ~~blueprint.update~~ | ~~blueprint_update~~ | ~~Gobernanza~~ | ~~w08~~ | ~~`update(bp_id, note?, section?, content?, puml?, path?)`~~ | ~~Update Blueprint progress.~~ **DEPRECATED — w08 conversacional: `blueprint.synthesize` reemplaza las 18 llamadas update en 1.** |
| **blueprint.synthesize** (NUEVO) | blueprint_synthesize | Gobernanza | w08 | `synthesize(bp_id, content, path?)` | **NUEVO — corazon del w08 conversacional.** Escribe las 18 secciones de la BLP en 1 llamada CORTEX. Reemplaza create + 18x update. |

## Modulo `skill` (6 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| skill.convert | skill_convert | Gobernanza | w07 | `convert(name, path?)` | Convert a skill from original format to CORTEX ultra-dense. Parte del flujo canonico w07. Paso de gobernanza del workflow. |
| skill.edit | skill_edit | Gobernanza | — | `edit(name, content?, section?, path?)` | Edit (read/write/section-edit) a skill file in .arqux/skills/. Operacion de ciclo de vida secundaria (muta estado). Se invoca ad-hoc cuando el flujo canonico no aplica (revertir, pausar, desvincular, etc.). |
| skill.evolve | skill_evolve | Gobernanza | w07 | `evolve(name, adaptation_id, apply?, path?)` | Apply an approved adaptation to a skill. Default is dry-run. Parte del flujo canonico w07. Paso de gobernanza del workflow. |
| skill.import | skill_import | Gobernanza | w07 | `import(source, name, content?, path?)` | Acquire a skill from external source, store original in originals/. Parte del flujo canonico w07. Paso de gobernanza del workflow. |
| skill.list | skill_list | Gobernanza | w07 | `list(path?)` | List all available skills in .arqux/skills/. Parte del flujo canonico w07. Paso de gobernanza del workflow. |
| skill.record | skill_record | Gobernanza | w07 | `record(name, expected, actual, reason, path?)` | Record a deviation (ADA) when a skill does not match the real context. Parte del flujo canonico w07. Paso de gobernanza del workflow. |

## Modulo `setup` (1 handlers)

| Handler (REGISTRY) | MCP tool | Categoria | En workflow | Firma | Para que / cuando usarlo |
|---|---|---|---|---|---|
| setup.plantuml | setup_plantuml | Utilidad | — | `plantuml(force?, path?)` | Download and install plantuml.jar to ~/.arqux/bin/. Inspeccion/render bajo demanda, sin side-effects. Se invoca ad-hoc (no es paso de un workflow). |

# 4. INDICE DE LOS 31 HANDLERS FUERA DE WORKFLOWS

Agrupados por razon de no aparecer en los diagramas canonicos:

**Utilidad / lectura (sin side-effects) — 8:**

`cortex.entry.delete`, `cortex.entry.get`, `cortex.entry.list`, `cortex.entry.move`, `cortex.render`, `cortex.render.diagram`, `cortex.render.validate_file`, `setup.plantuml`

**Ciclo de vida secundario (mutan, fuera del flujo feliz) — 23:**

`blueprint.define`, `blueprint.list`, `cycle.create`, `cycle.current`, `cycle.list`, `cycle.mature`, `evidence.list`, `evidence.read`, `project.bind`, `project.lessons`, `project.status`, `project.unbind`, `protocol.pause`, `protocol.release`, `protocol.resume`, `session.close`, `session.status`, `skill.edit`, `task.fail`, `task.list`, `task.read`, `workspace.lessons`, `workspace.status`

## 4.1 Clasificacion de los 31 handlers huérfanos

**Razon de exclusion:** No estan en diagramas de workflow canonico por diseno, no por omision.

| Grupo | Cantidad | Handlers | Justificacion |
|---|---|---|---|
| **Lectura/inspeccion ad-hoc** (utilidad, sin side-effects) | 8 | `cortex.entry.delete`, `cortex.entry.get`, `cortex.entry.list`, `cortex.entry.move`, `cortex.render`, `cortex.render.diagram`, `cortex.render.validate_file`, `setup.plantuml` | El agente los invoca bajo demanda cuando necesita consultar o renderizar. No pertenecen a un flujo fijo porque su uso es contextual. **No requieren workflow.** |
| **Ciclo de vida secundario** (mutan, pero fuera del flujo feliz) | 15 | `blueprint.list`, `cycle.create`, `cycle.current`, `cycle.list`, `cycle.mature`, `evidence.list`, `evidence.read`, `project.bind`, `project.lessons`, `project.status`, `project.unbind`, `skill.edit`, `task.fail`, `task.list`, `task.read` | Son operaciones de soporte que el agente invoca cuando el flujo canonico no aplica (revertir, pausar, desvincular, listar, etc.). Aparecen en situaciones de excepcion, no en el camino feliz. **No requieren workflow formal**, pero cada una deberia tener una entrada en `mcp-handlers.skill.md` §6 con `purpose` claro. |
| **Pausa/resume de sesion** | 3 | `protocol.pause`, `protocol.release`, `protocol.resume` | Operaciones de ciclo de vida de agente. Se invocan en momentos impredecibles (el Arquitecto pide pausa, o se libera un agente). **No requieren workflow canonico** — son interrupts del sistema. |
| **Cierre de sesion** | 2 | `session.close`, `session.status` | `session.close` se invoca al final de cualquier sesion, no solo de un workflow. Su uso es universal. **No requiere workflow dedicado.** |
| **Estado/lecciones de workspace** | 3 | `workspace.lessons`, `workspace.status`, `session.status` | Consultas de estado global. Arquitecto las pide ad-hoc. **No requieren workflow.** |

**Revision de seguridad (Heimdall):** Los 31 handlers estan correctamente fuera de workflows por diseno, no por omision. Sin embargo, 15 del grupo "ciclo de vida secundario" mutan estado sin un workflow que los audite. Recomendacion: anadir en `mcp-handlers.skill.md` una nota de auditoria en cada uno (`purpose_audit: "invocacion ad-hoc, revisar contexto antes de ejecutar"`).

# 5. ANALISIS DE CANAL: INTERNO vs EXTERNO

> Tesis del Arquitecto: ArqUX maneja dos canales de comunicacion con formatos y
> destinatarios opuestos. Declararlos explicitamente permite cualificar y cuantificar
> los cambios necesarios en los handlers.

## 5.1 Definicion de canales

| Canal | Destinatario | Formato | Propsito | Ejemplos |
|---|---|---|---|---|
| **I** (Interno) | agente ↔ agente, agente ↔ si mismo | CORTEX denso (sigilos, `$N`, attrs) | Minima transformacion, maximos tokens utiles, sin ruido visual. | `brain.cortex`, `identity.cortex`, entries de gobernanza. |
| **E** (Externo) | agente → humano | HCORTEX / markdown / BLP / PUML | Verificable visualmente, auditabilidad, formato expandido con explicaciones. | `docs/workflows/*.hcortex.md`, `BLP-*.hcortex.md`. |
| **B** (Ambos) | depende del contexto | necesita dos modos (I o E) | Un handler que sirve a agente y humano segun formato elegido. | `cortex.read(mode=native|ast|render)`, `task.read(format=cortex|hcortex)`. |

**Implicación:** un handler del canal I no debería parsear/transformar el CORTEX que
intercambia — lo recibe o entrega tal cual. Un handler del canal E debe expandir/
renderizar para consumo humano. Cuando un handler hoy hace ambas cosas mal (como
`cortex.read` que parsea y descarta el source), es candidato a separarse en dos modos.

## 5.2 Clasificacion por canal (por modulo)

### Modulo `workspace` (3)

| Handler | Canal | Fundamento |
|---|---|---|
| `workspace.init` | E | Inicializa archivos visibles. El `content` de salida es mensaje OUT. |
| `workspace.lessons` | E | Lista lecciones para humana. |
| `workspace.status` | E | Dashboard para humano. |

### Modulo `project` (5)

| Handler | Canal | Fundamento |
|---|---|---|
| `project.bind` | I | Vincula agente → identidad; operacion interna de gobernanza. |
| `project.init` | B | `seed` acepta CORTEX (I), pero el resultado es estructura visible (E). |
| `project.lessons` | E | Lista para humano. |
| `project.status` | E | Dashboard para humano. |
| `project.unbind` | I | Operacion interna de gobernanza. |

### Modulo `cycle` (5)

| Handler | Canal | Fundamento |
|---|---|---|
| `cycle.close` | I | Cierre de ciclo; operacion interna. |
| `cycle.create` | I | Creacion de ciclo; operacion interna. |
| `cycle.current` | I/E | Actualmente OUT-min (I); podria mostrar resumen humano (E). |
| `cycle.list` | I | Lista interna. |
| `cycle.mature` | I | Maduracion interna. |

### Modulo `task` (7)

| Handler | Canal | Fundamento |
|---|---|---|
| `task.claim` | I | Reclamo de tarea. |
| `task.complete` | I | Cierre de tarea. |
| `task.create` | **B → I** | Hoy acepta params descompuestos (estructurados). Deberia aceptar `content` CORTEX nativo (canal I). Los `ac`, `pre`, `proc`, `blk` son listas que se expresan mejor en CORTEX. |
| `task.fail` | I | Bloqueo interno. |
| `task.list` | I | Lista interna. |
| `task.read` | B | `format=cortex` → I; `format=hcortex` → E. ✅ Ya funciona con dos modos. |
| `task.update` | I | Nota interna. |

### Modulo `evidence` (3)

| Handler | Canal | Fundamento |
|---|---|---|
| `evidence.list` | I | Traza interna. |
| `evidence.read` | I | Lectura interna. |
| `evidence.record` | I | Registro interno. |

### Modulo `protocol` (4)

| Handler | Canal | Fundamento |
|---|---|---|
| `protocol.adopt` | I | Onboarding interno. |
| `protocol.pause` | I | Pausa interna. |
| `protocol.release` | I | Liberacion interna. |
| `protocol.resume` | I | Reanudacion interna. |

### Modulo `session` (5)

| Handler | Canal | Fundamento |
|---|---|---|
| `session.close` | **B → I** | Hoy `(summary,blps,tasks,decisions,gaps)` — 5 params. Deberia aceptar `content` con entrada SES CORTEX (I). |
| `session.context.get` | E | Header visible `⬡ agente | proyecto | scope` para humano. |
| `session.context.set` | **B → I** | Hoy `(project,scope,blp)` — 3 params. Deberia aceptar `content` con puntero CORTEX (I). |
| `session.resume` | I | Restauracion interna. |
| `session.status` | I | Metadata interna. |

### Modulo `cortex` (15)

| Handler | Canal | Fundamento |
|---|---|---|
| `cortex.entry.add` | **E → I** | Hoy `(section,sigil,name,value)`. Deberia aceptar `content` CORTEX nativo. Es el handler mas sintomatico del problema: para escribir 1 linea CORTEX debo generar 5 params estructurados. |
| `cortex.entry.delete` | I | Selector CORTEX como identificador — ya nativo. ✅ |
| `cortex.entry.get` | **I → B** | Hoy retorna lista de dicts. Podria retornar fragmento CORTEX (I) o tabla (E). |
| `cortex.entry.list` | **I → B** | Idem entry.get. |
| `cortex.entry.move` | I | Selector nativo. ✅ |
| `cortex.entry.update` | I | `set_` ya acepta attrs CORTEX (`key:val,key2:val2`). Semi-nativo. ✅ |
| `cortex.file.validate` | E | Diagnostico para humano. |
| `cortex.learn` | I | Scaneo interno del brain. |
| `cortex.learn.elevate` | I | Elevacion interna de candidatos. |
| `cortex.read` | **B → B** | Hoy retorna AST (ni I: no es CORTEX nativo, ni E: no es HCORTEX). Necesita `mode=native` (I) + mantener `ast` (hoy) + `render` (alias a cortex.render, E). |
| `cortex.render` | E | HCORTEX markdown para humano. ✅ |
| `cortex.render.diagram` | E | PUML renderizado para humano. ✅ |
| `cortex.render.validate_file` | E | Diagnostico D1-D5 para humano. ✅ |
| `cortex.verify` | I/E | Diagnostico estructurado; util para ambos. |
| `cortex.write` | I | `content` acepta CORTEX fuente nativo. ✅ |

### Modulo `identity` (1)

| Handler | Canal | Fundamento |
|---|---|---|
| `identity.record` | **E → I** | Hoy `(lesson,kind,cause,prevention)` — 5 params. Deberia aceptar `content` CORTEX ($5/LNG:lesson{...}). La leccion es CORTEX, no params sueltos. |

### Modulo `blueprint` (18)

| Handler | Canal | Fundamento |
|---|---|---|
| `blueprint.ac` | I | Verificacion interna de AC. |
| `blueprint.approve` | I | Aprobacion interna. |
| `blueprint.assign` | I | Asignacion interna. |
| `blueprint.block_for_architect` | I | Bloqueo interno. |
| `blueprint.cancel` | I | Cancelacion interna. |
| `blueprint.claim` | I | Reclamo interno. |
| `blueprint.complete` | I | Cierre interno. |
| `blueprint.create` | I | Creacion interna. |
| `blueprint.define` | **E → I** | Hoy 11 parametros (pre, scope, exclusions, ac, procedure, validations, technical_design, operational_design, risks, blocking_rule). Deberia aceptar `content` CORTEX con las secciones del blueprint. Es el caso mas extremo de params descompuestos. |
| `blueprint.fail` | I | Bloqueo interno. |
| `blueprint.gate` | I | Gate interno. |
| `blueprint.list` | I | Lista interna. |
| `blueprint.mature` | I | Maduracion interna. |
| `blueprint.re_delegate` | I | Re-delegacion interna. |
| `blueprint.read` | B | `format=cortex` → I; `format=hcortex` → E. ✅ Ya funciona con dos modos. |
| `blueprint.ready` | I | Declaracion interna. |
| `blueprint.task` | I | Checkpoint interno de tarea. |
| `blueprint.update` | I | Actualizacion interna de seccion. |

### Modulo `skill` (6)

| Handler | Canal | Fundamento |
|---|---|---|
| `skill.convert` | I | Conversion interna a CORTEX. |
| `skill.edit` | I | `content` acepta CORTEX. ✅ |
| `skill.evolve` | I | Evolucion interna. |
| `skill.import` | I | Adquisicion interna. |
| `skill.list` | I | Lista interna. |
| `skill.record` | **E → I** | Hoy 4 params (name, expected, actual, reason). Deberia aceptar `content` CORTEX con ADA. |

### Modulo `setup` (1)

| Handler | Canal | Fundamento |
|---|---|---|
| `setup.plantuml` | E | Utilidad para humano. |

## 5.3 Cuantificacion del cambio

### Por canal actual vs deseado

| Handler | Canal hoy | Canal deseado | Cambio necesario |
|---|---|---|---|
| `cortex.entry.add` | E (5 params) | I (1 content) | Aceptar `content` CORTEX nativo. |
| `cortex.read` | B mal (AST mixto) | B bien (mode=native + ast + render) | Añadir `mode=native` que retorne `.cortex` fuente crudo. |
| `task.create` | B (8 params) | I (1 content) | Aceptar `content` CORTEX. |
| `blueprint.define` | E (11 params) | I (1 content) | Aceptar `content` CORTEX. |
| `identity.record` | E (5 params) | I (1 content) | Aceptar `content` CORTEX. |
| `skill.record` | E (4 params) | I (1 content) | Aceptar `content` CORTEX. |
| `session.close` | E (5 params) | I (1 content) | Aceptar `content` CORTEX. |
| `session.context.set` | E (3 params) | I (1 content) | Aceptar `content` CORTEX. |
| `cortex.entry.get` | I (dicts) | B (format=native) | Añadir `format=native`. |
| `cortex.entry.list` | I (dicts) | B (format=native) | Añadir `format=native`. |

### Nuevos handlers propuestos (todos canal I)

**Meta-handlers CORTEX-native (fusionan llamadas existentes en 1):**

| Handler | Workflow | Reduce | Como funciona |
|---|---|---|---|
| `cortex.patch(path, deltas)` | w05/w09/w11 | 3-5 → 1 | Aplica add+update+delete atomicos en 1 llamada via texto CORTEX. Incluye verify + validate interno. |
| `blueprint.synthesize(bp_id, content)` | w08 | **18 → 1** | Colapsa 18 `blueprint.update` en 1 llamada. Acepta CORTEX con las 18 secciones. |
| `task.run(obj, priority, content, lessons?)` | w04 | 5 → 1 | Agrupa create + claim + execute + evidence + complete + identity.record en 1 llamada. |
| `skill.install(source, name)` | w07 | 3+2 → 1 | Une `skill.import` + `skill.convert` en 1 llamada. Adquiere y convierte a CORTEX en un paso. |
| `session.handoff(to_agent)` | w10 | 4 → 1 | Agrupa read(identidades, mode=native) + session.context.set(content) + evidence.record. |
| `protocol.onboard(agent_id, role)` | w06 | 2 → 1 | Agrupa cortex.read(identity, mode=native) + protocol.adopt. |
| `blueprint.execute(bp_id)` | w08 | N → pocas | Agrupa assign + claim + loop(task+resume) + complete. Los gates humanos (gate/ready/approve/ac) quedan SEPARADOS. |
| `context.full(project, scope)` | w03 | 3 → 1 | Agrupa cortex.read(brain, native) + cortex.read(meta-brain, native) + session.context.get + project.status. |
| `session.bootstrap()` | w01/w03/w06/w10 (w00) | N → 1 | **w00 transversal.** Detecta `.arqux/`, carga identidad activa (mode=native), verifica rol en AGENTS.md, presenta contexto completo. Elimina el preambulo repetido en 4 workflows. |
| `record_lesson(content)` | w04/w05/w07/w11 | 2 → 1 | Unifica identity.record + skill.record en un solo paso compartido de aprendizaje, evitando duplicar la logica de sintesis LNG/ADA entre workflows. |

**Utilidades CORTEX-native (nuevos handlers de referencia/apoyo):**

| Handler | Tipo |
|---|---|
| `cortex.ref(query)` | **Referencia CORTEX/HCORTEX para agentes.** Consulta sigilos, formatos, plantillas y selectores en CORTEX nativo. El agente no necesita memorizar sintaxis — pregunta y recibe el fragmento exacto listo para copiar/usar. |
| `cortex.format(texto_suelto)` → `cortex_valido` | Utilidad I: formatea/valida CORTEX suelto a CORTEX canonico. **Lo provee CODEC-CORTEX**, no un handler nuevo — solo exponerlo como handler. |

> **Detalle de `cortex.ref(query)`:** Devuelve CORTEX nativo (texto, canal I). Queries disponibles:
>
> | Query | Devuelve | Para qué |
> |---|---|---|
> | `sigils` | Tabla de sigilos canónicos (IDN, OBJ, WRK, FCS, LNG, TK, AC, AX, etc.) | Qué sigilo usar en cada caso |
> | `entry` | Formato de entrada CORTEX con ejemplos (attrs vs cuerpo) | Cómo escribir `content=` en los handlers |
> | `selector` | Sintaxis de selectores CORTEX (`$N/SIGIL:name`, `SIGIL:*`, `~` para update) | Cómo referenciar entradas existentes |
> | `hcortex` | Estructura completa de documento HCORTEX ($0, headers, PUML D1-D5, tables, backmatter $11) | Cómo armar los docs correctamente |
> | `template:task` | Plantilla CORTEX de tarea lista para `task.create(content=...)` | Copiar-pegar-adaptar |
> | `template:lesson` | Plantilla LNG para `identity.record(content=...)` | Idem |
> | `template:blueprint` | Plantilla de secciones para `blueprint.synthesize(content=...)` | Idem |
> | `template:hcortex` | Esqueleto HCORTEX con headers, tables, PUML y backmatter $11 | Idem |
> | `all` | Todo el spec completo | Carga única de contexto inicial |
>
> El spec vive como constante CORTEX embebida en el handler, accesible sin depender del workspace.
> Sin este handler, el agente escribe CORTEX a ciegas.

### Resumen cuantitativo

| Metrica | Valor |
|---|---|
| Handlers que ya estan bien en su canal (I native / E hcortex) | ~63 de 73 |
| Handlers que necesitan cambio de canal (E → I, aceptar `content`) | **8** |
| Handlers que necesitan modo adicional (I + E via `format`/`mode`) | **3** (`cortex.read`, `cortex.entry.get`, `cortex.entry.list`) |
| Nuevos meta-handlers propuestos (fusionan llamadas) | **10** (patch, synthesize, task.run, skill.install, session.handoff, protocol.onboard, blueprint.execute, context.full, session.bootstrap, record_lesson) |
| Nuevas utilidades propuestas (referencia/apoyo) | **2** (`cortex.ref`, `cortex.format` via CODEC-CORTEX) |
| Reduccion maxima de llamadas por operacion | De 18 (`blueprint.update`) a 1 (`blueprint.synthesize`) |
| Reduccion de params por handler | De 11 (`blueprint.define`) a 1 (`content`) |

### Orden de implementacion recomendado (revisado por Heimdall)

Basado en dependencias e impacto. **Revision de seguridad:** 9 hallazgos (H-01 a H-09)
identificados por Heimdall han sido incorporados al orden.

| Prioridad | Que | Por que | Hallazgos resueltos |
|---|---|---|---|
| **P1** | `cortex.ref` (handler + spec embebido) | Autocontenido, sin dependencias. Da al agente la herramienta para producir CORTEX correcto ANTES de tocar el resto. Sin el, los `content=` de los demas handlers se escriben a ciegas. | — |
| **P0.5** | `cycle.mature()` validar compuertas + `cycle.validate()` nuevo | H-09: ciclo se madura sin validar quality gates. Sin esto, los BLPs de P1-P7 se crean en un ciclo sin compuertas. **Arreglar antes de implementar cualquier mejora.** | H-09 |
| **P2-a** | `cortex.read(mode=native)` | **Priorizado antes de `entry.add`.** El bug (H-04) de `read_write.py:43-49` descarta el source CORTEX. Sin mode=native, el agente no puede leer CORTEX fielmente, lo que hace imposible editar o re-emitir. `entry.add` necesita mode=native para leer el archivo destino y verificar el estado actual. **Dependencia critica temprana.** | H-04 |
| **P2-b** | `cortex.entry.add(content)` + `cortex.entry.get|list(format=native)` | Anadir `content` como alternativa a params descompuestos. `format=native` en get/list permite al agente leer CORTEX como texto y re-emitirlo sin reconstruccion del AST. | H-04, H-08 |
| **P3** | `session.bootstrap()` (w00) | Elimina el preambulo repetido en 4 workflows. Depende de P2-a (mode=native para leer identidades). Mayor impacto transversal. | H-03 (degraded mode documentado en §6.1) |
| **P4** | `identity.record(content)` + `skill.record(content)` + `session.context.set(content)` + `session.close(content)` + `task.create(content)` + `blueprint.define(content)` | Anadir `content=` a los 6 handlers restantes de params descompuestos. Dependen de P2 como referencia de diseno. | H-08 |
| **P5** | `cortex.patch` + `blueprint.synthesize` | Meta-handlers de mutacion atomica. Dependen de P2 + P4 (los handlers base ya aceptan `content`). | H-05 (dependencias explicitas en §6.12) |
| **P6** | `task.run` + `skill.install` + `session.handoff` + `protocol.onboard` + `blueprint.execute` + `context.full` + `record_lesson` | Meta-handlers de flujo completo. Dependen de P4/P5. | H-05 |
| **P7** | `cortex.entry.get|list(format=native) restante` + `cortex.write(force promoted)` + `cortex.format` (exponer CODEC-CORTEX) | Utilidades restantes. Baja prioridad, alta utilidad. | — |

**Gobernanza de fases:** Cada fase P1-P7 debe crear su propio BLP con gates de verificacion
antes de pasar a la siguiente. `blueprint.gate` entrega la fase completada; `blueprint.approve`
autoriza la siguiente. Sin esta cadena de gates, se corre el riesgo de implementar P3 sobre
un P2 no verificado.

**Nota:** Ningun paso requiere cambios en los handlers de gates humanos (gate, ready, approve,
ac, block_for_architect, claim, complete, fail, cancel, list, read). Esos quedan ASIS
permanentemente — requieren intervencion del Arquitecto/Auditor y no deben automatizarse.

---

## 5.4 Prototipo del parametro `content` (H-08)

**Contexto (hallazgo Heimdall H-08):** 8 handlers necesitan un parametro `content` alternativo
a los params descompuestos. Sin un prototipo canonico, cada implementador puede interpretar
el formato, posicion y obligatoriedad de forma distinta.

**Prototipo canonico:**

| Aspecto | Especificacion |
|---|---|
| Nombre | `content` |
| Tipo | string (texto CORTEX valido) |
| Posicion | ultimo parametro antes de `path?`, despues de todos los existentes |
| Obligatoriedad | opcional (`content?`) — coexiste con params actuales |
| Prioridad | Si `content` esta presente, los params descompuestos se IGNORAN (el CORTEX es la unica fuente) |
| Formato | CORTEX nativo, NO JSON, NO markdown. Con sigilos, `$N`, attrs. |
| Validacion | El handler debe pasar `content` por `cortex.verify` antes de procesarlo. Si falla, error con detalle de la linea/entry invalida. |
| Error si ambos | Si se proveen `content` Y params descompuestos simultaneamente, el handler debe rechazar con error: "Provide content OR individual params, not both." |

**Ejemplo de comportamiento:**

```
# Hoy:
cortex.entry.add(path="brain.cortex", section="$5", sigil="LNG",
                 name="lesson_01", value="texto")

# Con content:
cortex.entry.add(path="brain.cortex",
                 content="$5/LNG:lesson_01{type:process, lesson:\"texto\"}")
```

**Handlers que adoptan este prototipo:** `cortex.entry.add`, `identity.record`,
`skill.record`, `session.close`, `session.context.set`, `task.create`,
`blueprint.define`, `cortex.entry.get(list format=native)`.

---

## 5.5 Reglas de enrutamiento de canal I/E/B (H-06)

**Contexto (hallazgo Heimdall H-06):** La clasificacion por canal (I/E/B) define el formato
de entrada y salida de cada handler, pero no hay reglas sobre:

- Que pasa si un handler canal I recibe entrada en formato E (HCORTEX/markdown)?
- Que pasa si un handler canal E recibe entrada en formato I (CORTEX denso)?
- Quien decide el canal activo en handlers canal B?

**Reglas de enrutamiento:**

| # | Regla | Handler aplica |
|---|---|---|
| R1 | **Canal I estricto:** el handler SOLO acepta CORTEX nativo. Si recibe HCORTEX/markdown, rechaza con error `ERR:format{ expected:"CORTEX", got:"markdown" }`. | `cortex.entry.*`, `identity.*`, `blueprint.*`, `task.*`, `skill.*`, `cycle.*`, `evidence.*`, `protocol.*` (modo I) |
| R2 | **Canal E estricto:** el handler SOLO produce HCORTEX/markdown. Si recibe CORTEX nativo como entrada, lo interpreta como contenido a renderizar. | `workspace.*`, `project.lessons`, `project.status`, `setup.*` |
| R3 | **Canal B por `mode`:** el handler canal B determina el formato via parametro `mode` (o `format`). Si no se especifica, el handler debe usar un default seguro (recomendado: `mode=ast` para `cortex.read`, `mode=cortex` para `task.read`). | `cortex.read(mode=native|ast|render)`, `cortex.entry.get(format=native|default)`, `cortex.entry.list(format=native|default)`, `task.read(format=cortex|hcortex)`, `project.init(seed)` |
| R4 | **Canal B por `content`:** si el handler acepta `content`, la presencia de `content` implica canal I; la ausencia implica modo descompuesto (canal E). | Todos los handlers con `content?` (ver §5.4) |
| R5 | **Agente declara canal:** en handlers canal B, el agente DEBE especificar `mode`/`format`. Si omite, el handler lo infiere: si el input es `content` → I; si son params descompuestos → E. | Validacion en runtime del MCP handler |
| R6 | **No hay conversion automatica I↔E:** un handler canal I no debe "adivinar" que el usuario queria HCORTEX. Si el agente necesita conversion, debe usar `cortex.render` explicitamente. | — |

**Implementacion:** Las reglas R1-R6 deben reflejarse en `mcp-handlers.skill.md` §8
(nueva seccion de clasificacion de canal) como referencia rapida. R5 ademas debe tener
 una asercion en los tests de cada handler canal B.

---

## 5.6 Invarianza de estado: validar antes de mutar (H-09)

**Contexto (hallazgo Heimdall H-09, derivado de la revision de CYCLE-02/CYCLE-03):**

`cycle.mature()` (`cycle.py:194-302`) transiciona el ciclo de `draft` a `ready` sin
validar las compuertas de calidad definidas en el MANIFEST.md. `_read_quality_gates()`
existe y se usa en `blueprint.ready` (`lifecycle.py:359`) para rechazar blueprints
inmaduros, pero `cycle.mature` nunca la llama. Resultado: ciclos vacios aprobados.

**Causa raiz:** El sistema de compuertas de calidad se implemento en blueprints
(`_read_quality_gates` + `blueprint.ready`) pero el handler analogo de ciclo
(`cycle.mature`) quedo sin la misma validacion. Es un bug de inconsistencia en
la aplicacion del patron "validar invariantes antes de mutar".

**Regla de gobernanza:**

| # | Regla | Handler aplica |
|---|---|---|
| R7 | **Validar invariantes antes de mutar:** todo handler que transicione estado (draft→ready, defined→maturing, etc.) debe leer y verificar las compuertas de calidad del artefacto destino ANTES de modificar el estado. Si alguna compuerta es `false`, el handler rechaza con error listando las compuertas fallidas. | `cycle.mature`, `blueprint.ready`, `blueprint.mature`, `blueprint.gate`, y cualquier futuro handler de transicion. |

**Correccion en P1-P7:**

- `cycle.mature()` debe llamar `_read_quality_gates(fm)` y rechazar si hay compuertas
  en `false`. El gobernador debe llenar el MANIFEST.md primero.
- `cycle.validate(path?)` como nuevo handler utilidad que lista el estado de las
  6 compuertas sin mutar nada. Canal I, lectura pura.
- `blueprint.ready` ya lo hace bien (usar como patron).
- Esta regla debe anadirse a `mcp-handlers.skill.md` como `HDL:cycle.validate` y
  como `AXM:validate_before_mutate` en el skill de workflows.

**Impacto en P1-P7:** Insertar como **P0.5** entre P1 y P2, o como parte de P2-a:
arreglar `cycle.mature()` antes de tocar cualquier otra cosa, porque la falta de
validacion de ciclo invalida cualquier mejora que construyamos encima (los BLPs
de P1-P7 se crearian en un ciclo sin compuertas).

---

# 6. VISION DE CORRECCION POR WORKFLOW

> Mapeo de cada workflow a los handlers que cambian, el tipo de cambio y la secuencia
> optimizada. El diagrama PUML detallado de cada secuencia optimizada esta en
> `docs/workflows/wXX.hcortex.md §6`.

## 6.1 w01 — Workspace Init

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `workspace.init(path)` | Sin cambio | `workspace.init(path)` | E |

**Vision:** Sin cambio en handlers. La optimizacion real esta en el preambulo (detectar `.arqux/` + leer AGENTS.md) que se repite en w01/w03/w06/w10. Se resuelve con `session.bootstrap()` (w00, P3) — no en w01 mismo.

**Modo degradado (Heimdall H-03):** Si `session.bootstrap()` falla, el agente debe
ejecutar el preambulo manualmente (detectar `.arqux/` + `cortex.read(mode=native)` +
`project.status` + `session.resume`). Se pierde la consolidacion pero no se bloquea
el workflow. El `session.bootstrap` debe documentar en su spec los pasos de fallback.

## 6.2 w02 — Govern Project

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `project.init(name, seed?)` | Sin cambio (seed ya CORTEX nativo) | `project.init(name, seed?)` | B |

**Vision:** Unico handler del sistema que ya hace bien el canal I. Sirve como patron para los demas. Sin cambio requerido.

## 6.3 w03 — Session Start

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `cortex.read(path)` | `mode=native` | `cortex.read(path, mode=native)` | B |
| `session.context.get` | Sin cambio | `session.context.get` | E |
| — | **NUEVO** | `context.full(project, scope)` | B |

**Vision:** Las 2 lecturas de brain pasan a `mode=native` (P2). Opcionalmente `context.full` (P6) agrupa las 3 llamadas en 1. Reduccion: 3 → 1 (67%).

## 6.4 w04 — Reactive Task

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `task.create(obj, pre, proc, ac, blk, assignee, complexity, priority)` | +`content` | `task.create(content=...)` | I |
| `task.claim(task_id)` | Sin cambio | `task.claim(task_id)` | I |
| `evidence.record(task_id, kind, payload)` | Sin cambio | `evidence.record(...)` | I |
| `task.complete(task_id, evidence)` | Sin cambio | `task.complete(...)` | I |
| `identity.record(lesson, kind, cause, prevention)` | +`content` | `identity.record(content=...)` | I |
| — | **NUEVO** | `task.run(obj, priority, content, lessons?)` | I |

**Vision:** `task.create` acepta `content` CORTEX (P4). `identity.record` acepta `content` (P4). El mayor impacto es `task.run` (P6): agrupa 5 llamadas en 1, incluyendo la leccion. Reduccion: 5 → 1 (80%) con `task.run`.

## 6.5 w05 — Identity Evolution

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `cortex.entry.add(path, section, sigil, name, value)` | +`content` | `cortex.entry.add(path, content=...)` | I |
| `identity.record(lesson, kind, cause, prevention)` | +`content` | `identity.record(content=...)` | I |
| `evidence.record(...)` | Sin cambio | `evidence.record(...)` | I |
| — | **NUEVO** | `cortex.patch(path, deltas)` | I |

**Vision:** `cortex.entry.add` con `content` (P2) colapsa 5 params en 1. `identity.record` con `content` (P4). Con `cortex.patch` (P5), add+record se fusionan en 1 llamada atomica. Reduccion: 3 → 1 (67%).

## 6.6 w06 — Agent Adoption

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `cortex.read(identity.cortex)` | `mode=native` | `cortex.read(path, mode=native)` | B |
| `protocol.adopt(agent_id, role)` | Sin cambio | `protocol.adopt(agent_id, role)` | I |
| — | **NUEVO** | `protocol.onboard(agent_id, role)` | I |

**Vision:** `cortex.read` con `mode=native` (P2). Opcionalmente `protocol.onboard` (P6) agrupa read+adopt en 1. Reduccion: 2 → 1 (50%).

## 6.7 w07 — Skill Lifecycle

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `skill.import(source, name, content?)` | Sin cambio | `skill.import(...)` | I |
| `skill.convert(name)` | Sin cambio | `skill.convert(name)` | I |
| `skill.list(path?)` | Sin cambio | `skill.list(path?)` | I |
| `skill.record(name, expected, actual, reason)` | +`content` | `skill.record(content=...)` | I |
| `skill.evolve(name, adaptation_id, apply?)` | Sin cambio | `skill.evolve(...)` | I |
| — | **NUEVO** | `skill.install(source, name)` | I |

**Vision:** `skill.record` con `content` (P4). `skill.install` (P6) une import+convert en 1. Reduccion: 3+2 → 2+ (50%).

## 6.8 w08 — Blueprint Lifecycle ⭐

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `cortex.read(brain.cortex)` | `mode=native` | `cortex.read(path, mode=native)` | B |
| `session.resume(path?)` | Sin cambio | `session.resume(path?)` | I |
| `blueprint.create(obj, cycle?)` | Sin cambio | `blueprint.create(obj, cycle?)` | I |
| `blueprint.update(bp_id, section, content)` ×**18** | → **NUEVO** | `blueprint.synthesize(bp_id, content)` | I |
| `blueprint.claim(bp_id)` | Sin cambio | `blueprint.claim(bp_id)` | I |
| `blueprint.task(bp_id, task_id, status)` | Sin cambio | `blueprint.task(...)` | I |
| `blueprint.complete(bp_id, evidence)` | Sin cambio | `blueprint.complete(...)` | I |
| `blueprint.ac(bp_id, ac_id, status, ...)` | Sin cambio | `blueprint.ac(...)` | I |
| `blueprint.gate/ready/approve/block` | Sin cambio | (gates humanos, ASIS) | I |
| `cycle.close(cycle_id, summary)` | Sin cambio | `cycle.close(...)` | I |
| `cortex.learn/elevate` | Sin cambio | `cortex.learn/elevate` | I |
| — | **NUEVO** | `blueprint.execute(bp_id)` | I |

**Vision:** Esta es la correccion de MAYOR impacto del sistema. `blueprint.synthesize` (P5) colapsa **18 `blueprint.update` en 1 llamada** (94% de reduccion). `cortex.read` con `mode=native` (P2). `blueprint.execute` (P6) opcionalmente agrupa claim+loop+complete. Los gates humanos (gate/ready/approve/ac/block) quedan EXACTAMENTE IGUAL. Reduccion total por blueprint: ~30 → ~13 (57%).

## 6.9 w09 — CRUD Blocked

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `cortex.entry.update(path, selector, set_, force)` | Sin cambio (set_ ya CORTEX nativo) | `cortex.entry.update(path, selector, set_, force)` | I |
| `cortex.verify(path)` | Sin cambio | `cortex.verify(path)` | I |
| `cortex.file.validate(path, fix?)` | Sin cambio | `cortex.file.validate(path, fix?)` | I |
| — | **NUEVO** | `cortex.patch(path, deltas)` | I |

**Vision:** `cortex.entry.update(set_)` YA acepta formato attrs CORTEX (`entries.py:106-114`). Sin cambio urgente. `cortex.patch` (P5) ofrece fusionar update+verify+validate en 1 llamada. Reduccion: 3 → 1 (67%) con `cortex.patch`.

## 6.10 w10 — Identity Handoff

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `cortex.read(identity.cortex)` | `mode=native` | `cortex.read(path, mode=native)` | B |
| `cortex.read(destino.cortex)` | `mode=native` | `cortex.read(path, mode=native)` | B |
| `session.context.set(project, scope, blp)` | +`content` | `session.context.set(content=...)` | I |
| `evidence.record(...)` | Sin cambio | `evidence.record(...)` | I |
| — | **NUEVO** | `session.handoff(to_agent)` | I |

**Vision:** `cortex.read` con `mode=native` (P2). `session.context.set` con `content` (P4). `session.handoff` (P6) agrupa 4 llamadas en 1. Reduccion: 4 → 1 (75%).

## 6.11 w11 — Cortex File Repair

| Handler hoy | Cambio | Handler optimizado | Canal |
|---|---|---|---|
| `cortex.verify(path)` | Sin cambio | `cortex.verify(path)` | I |
| `cortex.read(path)` | `mode=native` | `cortex.read(path, mode=native)` | B |
| `cortex.write(path, content, force)` | Sin cambio (content ya CORTEX nativo) | `cortex.write(path, content, force)` | I |
| `cortex.entry.add(path, section, sigil, name, value)` | +`content` | `cortex.entry.add(path, content=...)` | I |
| `identity.record(lesson, kind, cause, prevention)` | +`content` | `identity.record(content=...)` | I |
| — | **NUEVO** | `cortex.migrate(path)` | I |
| — | **NUEVO** | `cortex.patch(path, deltas)` | I |

**Vision:** `cortex.entry.add` con `content` (P2). `identity.record` con `content` (P4). `cortex.migrate` (P5) promueve el interno `state.migrate_cortex_file` a handler MCP: backup+read+write+verify en 1 sola llamada. Con `cortex.patch` (P5) todo se fusiona. Reduccion: 5 → 1-2 (60-80%).

## 6.12 Resumen de correccion por workflow

| Workflow | Llamadas hoy | Llamadas optimo | Handlers modificar | Handlers nuevos | Reduccion | Depende de |
|---|---|---|---|---|---|---|
| **w00 triage** | **nuevo** | **2** | **0** | **0** | **—** | **—** (usa solo handlers existentes) |
| w01 workspace | 1 | 1 | 0 | 0 | 0% | — |
| w02 project | 1 | 1 | 0 | 0 | 0% | — |
| w03 session | 3 | 1-3 | 1 (`cortex.read mode`) | 1 (`context.full`) | 0-67% | **P2-a** (mode=native) para alcanzar el maximo |
| w04 task | 5 | 1-5 | 2 (`content`) | 1 (`task.run`) | 0-80% | **P4** (content) + **P6** (task.run) para 80% |
| w05 identity | 3 | 1-3 | 2 (`content`) | 1 (`cortex.patch`) | 0-67% | **P2-b** (entry.add content) + **P5** (patch) |
| w06 adoption | 2 | 1-2 | 1 (`cortex.read mode`) | 1 (`protocol.onboard`) | 0-50% | **P2-a** (mode=native) + **P6** (onboard) |
| w07 skill | 3-5 | 2-4 | 1 (`content`) | 1 (`skill.install`) | 0-50% | **P4** (skill.record content) + **P6** (install) |
| **w08 blueprint** | **~30** | **~13** | **1 (`cortex.read mode`)** | **2 (synthesize, execute)** | **~57%** | **P5** (synthesize) — el 90% de la reduccion es synthesize |
| w09 crud | 3 | 1-3 | 0 | 1 (`cortex.patch`) | 0-67% | **P5** (patch) |
| w10 handoff | 4 | 1-4 | 2 (`mode` + `content`) | 1 (`session.handoff`) | 0-75% | **P2-a** (mode) + **P4** (content) + **P6** (handoff) |
| w11 repair | 5 | 1-2 | 3 (`mode` + `content` ×2) | 2 (`migrate`, `patch`) | 60-80% | **P2** (mode+content) + **P5** (patch+migrate) |
| **Total sistema** | **~60** | **~27-42** | **8 modificar + 3 modo** | **10 meta + 2 util** | **~30-55%** | **P2-a es el cuello de botella** — sin mode=native, las reducciones de w03/w06/w10/w11 son 0% |

**Vision general:** 12 workflows (w00-w11). w00 es nuevo y transversal — antecede a w02, w03, w04, w08 y cycle.create. Abarca 5 direcciones de acción: BLP, tarea ad-hoc, nuevo ciclo, cambio de proyecto, consulta. La correccion transforma el surface MCP de 73+2 handlers (synthesize, context.full) con capacidad CORTEX-native. 10 handlers del flujo anterior de w08 quedan deprecados en el flujo conversacional.

---

# 7. VISION DE CORRECCION DE SKILLS

> Los skills en `src/arqux/skills/*.skill.md` son la fuente de verdad para el agente sobre
> como operar los handlers y workflows. Deben reflejar el nuevo diseno de canal I/E/B
> una vez que se implemente.

## 7.1 `mcp-handlers.skill.md`

**Archivo:** `src/arqux/skills/mcp-handlers.skill.md` (199 lineas, 73 handlers en §6)

**Que debe cambiar:**

| Seccion | Hoy | Correccion necesaria |
|---|---|---|
| §2 header `AXM:governance_vs_utility` | Clasifica handlers en gobernanza/utilidad | Anadir referencia a canal I/E/B (`AXM:channel_classification`) |
| §6 `HDL:cortex.entry.add` | `signature:"entry.add(path, section, sigil, name, value, create_section?, force?)"` | Anadir `content?` como alternativa CORTEX-native a section+sigil+name+value |
| §6 `HDL:cortex.read` | `signature:"read(path)"` | Anadir `mode?` (native/ast/render) |
| §6 `HDL:cortex.entry.get` | `signature:"entry.get(path, selector)"` | Anadir `format?` (native/default) |
| §6 `HDL:cortex.entry.list` | `signature:"entry.list(path, section?, sigil?)"` | Anadir `format?` |
| §6 `HDL:identity.record` | `signature:"record(lesson, kind?, cause?, agent_id?, path?)"` | Anadir `content?` como alternativa CORTEX-native |
| §6 `HDL:skill.record` | `signature:"record(name, expected, actual, reason, path?)"` | Anadir `content?` |
| §6 `HDL:session.close` | `signature:"close(summary, blps?, tasks?, decisions?, gaps?, path?)"` | Anadir `content?` |
| §6 `HDL:session.context.set` | `signature:"context.set(project, scope, blp?, path?)"` | Anadir `content?` |
| §6 `HDL:task.create` | `signature:"create(obj, pre?, proc?, ac?, blk?, assignee?, complexity?, priority?, path?)"` | Anadir `content?` |
| §6 `HDL:blueprint.define` | `signature:"define(bp_id, pre?, scope?, exclusions?, ...)"` | Anadir `content?` |
| §6 header | `$6: QUICK REFERENCE — 73 HANDLERS` | Actualizar a `73 HANDLERS +12 PLANNED` |
| §6 (nuevas entradas) | No existen | Anadir `HDL:*` para los 12 nuevos handlers planificados (ver §5.5 de este catalogo) |
| §6 (canal) | Sin clasificacion de canal | Anadir `[Canal I/E/B]` en cada `purpose` |
| — | **NUEVA §8** | Anadir seccion `$8: CHANNEL CLASSIFICATION` como referencia rapida de I/E/B |

**Impacto:** 11 lineas de signature modificadas + 12 lineas nuevas + clasificacion de canal en los 73 existentes.

## 7.2 `workflows.skill.md`

**Archivo:** `src/arqux/skills/workflows.skill.md` (46 lineas, 11 workflows en §2)

**Que debe cambiar:**

| Seccion | Hoy | Correccion necesaria |
|---|---|---|
| §2 IDN:w01–w11 | 11 workflows | Anadir `IDN:w00` con `session.bootstrap()` como workflow transversal de bootstrap |
| §2 `purpose` de cada workflow | Descripcion actual | Anadir referencia a `docs/workflows/wXX.hcortex.md §6` para la version optimizada CORTEX-native |
| §3 (opcional) | No existe | Podria anadirse un `STP:triage` actualizado que considere si usar el flujo clasico (w04/w08) o el optimizado CORTEX-native |

**Impacto:** 1 nueva entrada w00 + 11 lineas de `purpose` actualizadas.

## 7.3 `cortex.skill.md` — ¿Sigue haciendo falta?

**Archivo:** `src/arqux/skills/cortex.skill.md` (252 lineas)

**Analisis de contenido actual vs `cortex.ref`:**

| Tipo | % del skill | Lo cubre `cortex.ref`? | Que hacer |
|---|---|---|---|
| AXM (reglas de gobernanza: `format`, `no_prose_in_state`, `stable_sigils`, `memory_format`, `one_format_everywhere`, `internal_cortex`, `memory_evolves`) | ~60% | **NO** — son principios de diseno, no sintaxis. | **Conservar en el skill.** Son la constitucion del formato. |
| STP `memory_examples` (ejemplos de LNG, KNW, SES) | ~10% | **SI** — `cortex.ref(template:lesson)` da la plantilla exacta. | **Eliminar del skill.** Delegar a `cortex.ref`. |
| STP `internal_templates` (plan, session, todo) | ~10% | **SI** — `cortex.ref(template:task|blueprint)` da plantillas mas completas. | **Eliminar del skill.** Delegar a `cortex.ref`. |
| §4 CORTEX-OUT (perfiles de salida) | ~15% | **NO** — es logica de output protocol, no sintaxis CORTEX. | **Conservar.** Es parte del protocolo de respuesta, no de formato de datos. |
| §0 glossary | ~5% | **SI parcial** — `cortex.ref(sigils)` cubre la tabla de sigilos. | **Simplificar.** Solo dejar los sigilos base (IDN, AXM, STP, OUT, FMT) y referenciar `cortex.ref(sigils)` para el listado completo. |

**Conclusion:**

```
cortex.skill.md (252 lineas)
  │
  ├── 60% AXM (reglas) ── QUEDA ── son constitucion, no referencia
  ├── 20% ejemplos/plantillas ── SE ELIMINA ── lo da cortex.ref
  ├── 15% CORTEX-OUT ── QUEDA ── es protocolo de salida
  └──  5% glossary ── SE SIMPLIFICA ── solo sigilos base, el resto via cortex.ref
```

**Propuesta de skill simplificado (~80 lineas):**

```
$0: GLOSSARY (solo IDN, AXM, STP, OUT, FMT — sigilos base del skill)
$1: AXIOMAS (AXM:format, no_prose_in_state, stable_sigils, memory_format,
             one_format_everywhere, internal_cortex, memory_evolves)
$2: CORTEX-OUT (perfiles MIN/WORK/AUDIT/FULL/ERROR — cuando usar cada uno)
$3: REFERENCIA (
      "Sintaxis → cortex.ref(entry|selector)"
      "Sigilos → cortex.ref(sigils)"
      "Plantillas → cortex.ref(template:*)"
      "Estructura HCORTEX → cortex.ref(hcortex)"
    )
```

**Impacto:** 252 → ~80 lineas (-68%). El skill deja de ser "documentacion viva + tutorial" y pasa a ser solo "constitucion del formato CORTEX". Toda la referencia y ejemplos se delegan al handler `cortex.ref`.

> **Nota de seguridad (Heimdall H-01):** cortex.skill.md debe mantenerse como
> **fallback local**, no como sustituto completo. Si el handler `cortex.ref` falla
> (runtime down, bug, breaking change), el skill es el unico recurso del agente para
> producir CORTEX valido. El skill propuesto (~80 lineas) es lo suficientemente pequeno
> para mantenerse manualmente. La regla: "cortex.ref como capa rapida, cortex.skill.md
> como capa resiliente."

## 7.4 `protocol.skill.md`, `diagram.skill.md`, `learning.skill.md`

**Estos skills no requieren cambios.** Sus handlers no tienen params descompuestos, no participan en el canal I/E/B de CORTEX-native, y sus flujos ya son eficientes.

| Skill | Razon |
|---|---|
| `protocol.skill.md` | Handlers simples (adopt/pause/release/resume). Sin params descompuestos. |
| `diagram.skill.md` | Solo PUML render. Canal E puro (humano). Sin cambio. |
| `learning.skill.md` | Solo `cortex.learn/elevate`. Canal I puro, sin params descompuestos. |

## 7.5 Resumen de correccion de skills

| Skill | Lineas | Handlers/sections afectados | Tipo de correccion | Prioridad |
|---|---|---|---|---|
| `mcp-handlers.skill.md` | 199 | 11 signatures + 12 new HDL + 73 canal tags | Modificar + anadir | **P1** (dependencia de todos los demas) |
| `workflows.skill.md` | 46 | w00 nuevo + 11 purpose actualizados | Anadir + modificar | P2 |
| `cortex.skill.md` | 252 → **~80** | 60% AXM conservado, 35% ejemplos delegado a `cortex.ref`, 5% glossary simplificado | **Simplificar drásticamente** (+ referenciar `cortex.ref`) | P3 |
| `protocol.skill.md` | 117 | 0 | Sin cambio | — |
| `diagram.skill.md` | 138 | 0 | Sin cambio | — |
| `learning.skill.md` | 85 | 0 | Sin cambio | — |

**El skill critico es `mcp-handlers.skill.md`:** es la unica fuente de verdad de las firmas de handlers y el primer lugar donde un agente busca como invocar un handler. Sin actualizarlo, los agentes no sabran que existe `content`, `mode=native` ni los nuevos meta-handlers.

---

# 8. HANDLERS DEPRECADOS POR W08 CONVERSACIONAL

**Motivacion:** La vision conversacional del Arquitecto reemplaza el flujo secuencial
de 18+ llamadas `blueprint.*` por una sesion de diseno de 4 handlers. 10 handlers
del flujo anterior quedan deprecados en w08.

## 8.1 Lista de deprecados

| Handler | Reemplazado por | Razon |
|---|---|---|
| `blueprint.create` | `blueprint.synthesize` | synthesize crea + llena en 1 paso |
| `blueprint.mature` | (la conversacion) | La maduracion es el dialogo mismo |
| `blueprint.update` x18 | `blueprint.synthesize` | 18 llamadas → 1 llamada CORTEX |
| `blueprint.gate` | (verificacion en dialogo) | Las compuertas se verifican durante la conversacion |
| `blueprint.assign` | (decidido en dialogo) | Quien ejecuta se define al conversar |
| `blueprint.claim` | (el agente es el ejecutor) | No hay rol separado de executor |
| `blueprint.ac` | (definido en dialogo) | Los ACs se definen y verifican durante la conversacion |
| `blueprint.re_delegate` | — | No hay fallo de AC post-aprobacion |
| `blueprint.block_for_architect` | — | El Arquitecto ya esta en la conversacion |
| `blueprint.approve` | (Arquitecto dice "ok") | La palabra del Arquitecto es approve |

## 8.2 Handlers que se conservan

| Handler | Para que |
|---|---|
| `blueprint.synthesize` | **NUEVO** — corazon del flujo conversacional |
| `context.full` | **NUEVO** — contexto completo en 1 llamada |
| `blueprint.ready` | Transicion formal a ejecucion |
| `blueprint.complete` | Marca ejecucion completada |
| `blueprint.task` | Checkpoint de tareas durante ejecucion |
| `blueprint.read` | Lectura de BLPs existentes |
| `blueprint.list` | Listar BLPs |
| `blueprint.fail` | Bloqueo por obstaculo imprevisto |
| `blueprint.cancel` | Cancelacion explicita |
| `blueprint.define` | Edicion manual excepcional |

## 8.3 Impacto en el sistema

| Aspecto | Antes | Despues | Cambio |
|---|---|---|---|
| Handlers en w08 | 20 | 6 activos + 2 nuevos | **-60%** |
| Llamadas por BLP | ~23 | ~4 | **-83%** |
| Interacciones humanas | 6+ | 3 | **-50%** |
| Roles necesarios | Gov + Exec + Aud + Arq | Solo Arquitecto | **-75%** |

> **Nota:** Los 10 handlers deprecados en w08 aun existen en el REGISTRY y pueden
> usarse en otros contextos (migracion, compatibilidad hacia atras, casos borde).
> No se eliminan del codigo — solo se marcan como no recomendados para el flujo
> principal de creacion de BLPs.

---

$11: CONCURRENCY
ERR:catalog{ version:"6", generated:"2026-07-12", source:"REGISTRY + mcp-handlers.skill.md + cortex-native affinity analysis (ALFRED) + audit (HEIMDALL H-01–H-09) + deprecacion w08 conversacional (ARQUITECTO) + w00 triage" }
