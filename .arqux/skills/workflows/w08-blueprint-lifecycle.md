$0

# -- $0: WORKFLOW W08 — BLUEPRINT LIFECYCLE (CONVERSACIONAL v2.0)
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# WRK   | workflow   | cuerpo     | B | Working        | Execution procedure
# LNG   | lesson     | cuerpo     | L | Episodic       | Note, handler list, reference
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram (custom)
# HDL   | handler    | attrs      | B | Semantic       | Handler reference (custom)

# Custom GSIG declarations for DIAG and HDL
GSIG:DIAG{name:"diagram", type:"cuerpo", risk:"B", layer:"Semantic", description:"PlantUML diagram"}
GSIG:HDL{name:"handler", type:"attrs", risk:"B", layer:"Semantic", description:"Handler reference", fields:"name,description"}


$1: IDENTITY

IDN:w08{ name:"Blueprint Lifecycle (Conversacional)", purpose:"Ciclo completo optimizado: triage → indagacion conversacional → sintesis autonoma (blueprint.synthesize, 1 llamada) → ready → ejecucion → verificacion → cierre. Reduccion: ~23→4 llamadas MCP (83%).", trigger:"Nueva funcionalidad, componente, o refactor que requiere diseno.", handlers:"4", reduction:"23→4 (83%)", version:"2.0" }


$2: STATE MACHINE DIAGRAM

DIAG:w08_sm{
@startuml
title Blueprint Lifecycle — State Machine (v2.0 Optimizado)

state "draft" as D
state "conversational_design" as CD
state "ready" as R
state "in_progress" as IP
state "review" as RV
state "done" as DN
state "blocked" as B
state "cancelled" as CN

[*] --> D : blueprint.synthesize
D --> CD : indagacion conversacional
CD --> R : blueprint.ready
R --> IP : blueprint.claim
IP --> RV : blueprint.complete
IP --> B : blueprint.fail
B --> D : re-plan
B --> CN : blueprint.cancel
RV --> DN : blueprint.approve
RV --> IP : re-delegate (max 3)
RV --> CN : 3rd fail
@enduml
}


$3: CONVERSATIONAL SEQUENCE DIAGRAM

DIAG:w08_conv{
@startuml
title w08 — Blueprint Lifecycle Conversacional (v2.0, ~4 llamadas)

actor "Arquitecto" as A
participant "Agente" as AG
participant "MCP Server" as S
participant "Handler: context.full" as HCTX
participant "Handler: blueprint.synthesize" as HSYN
participant "Handler: cortex.ref" as HREF
participant "Handler: cortex.render" as HREN
database "BLP / brain.cortex" as BL

== PASO 1: CONTEXTO (w01+w02+w03) ==
A -> AG: Saludo, proyecto, contexto
AG -> HCTX: context.full(proyecto, scope)
HCTX -> BL: project.status + cycle.current + cycle.list
HCTX --> AG: Ciclos activos, BLPs pendientes

== PASO 2: SELECCIONAR CICLO ==
A -> AG: Trabajamos en CYCLE-N
AG -> A: Ok. Ciclo activo.

== PASO 3: CONVERSACION DE DISENO ==
A -> AG: Necesito [descripcion del problema]
AG -> HREF: cortex.ref (consulta plantillas)
AG -> A: Preguntas para entender alcance...
A -> AG: Respuestas, ajustes...
note right
  Conversacion no estructurada.
  Agente propone, Arquitecto
  refina. Sin llamadas MCP.
end note

== PASO 4: SINTESIS AUTONOMA ==
AG -> HSYN: blueprint.synthesize(bp_id, content)
HSYN -> BL: 18 secciones en 1 llamada
HSYN --> AG: BLP-NNN sintetizada

== PASO 5: REVISION EXTERNA ==
A -> AG: Genera HCORTEX para revision
AG -> HREN: cortex.render(bp_id)
HREN --> AG: BLP-NNN.hcortex.md
AG -> A: Revisa en tu editor

== PASO 6: APROBACION ==
A -> AG: Aprobado
AG -> A: BLP-NNN lista para ejecucion
@enduml
}


$4: AXIOMS

AXM:w08_conversational{ El diseno de BLP es conversacional (no secuencial). Agente y Arquitecto conversan en lenguaje natural. El agente sintetiza las 18 secciones en 1 llamada via blueprint.synthesize. Esto reemplaza 18 llamadas blueprint.update + blueprint.create + blueprint.mature + blueprint.gate (~23 total). }

AXM:w08_synthesize{ blueprint.synthesize es el corazon del flujo: escribe las 18 secciones en 1 llamada CORTEX. Reemplaza: blueprint.create + 18x blueprint.update + blueprint.mature + blueprint.gate + blueprint.assign (~23→1). Reduccion: 83%. }

AXM:w08_coherence{ La sintesis debe ser coherente: objetivo (§2), alcance (§6), criterios (§12) y procedimiento (§11) alineados. El agente verifica internamente antes de presentar. }


$5: HANDLER REFERENCES (HDL)

HDL:context_full{ name:"context.full", description:"Agrupa project.status + cycle.current + cycle.list en 1 respuesta (P3)." }
HDL:blueprint_synthesize{ name:"blueprint.synthesize", description:"Escribe las 18 secciones de la BLP en 1 llamada CORTEX (P4). Handler principal de w08." }
HDL:cortex_ref{ name:"cortex.ref", description:"Consulta plantillas, sigilos y formatos CORTEX durante la conversacion (P1)." }
HDL:cortex_render{ name:"cortex.render", description:"Renderiza BLP a HCORTEX para revision externa (visor)." }


$6: WORKFLOW STEPS — SYNTHESIS

WRK:w08_synthesis{ status:"current", owner:"agente", survive:"yes", action:"sintetizar BLP desde conversacion", procedure:"1. Escuchar la vision del Arquitecto en lenguaje natural. NO escribir BLP aun. 2. Formular preguntas para completar el mapa: alcance, limites, criterios, riesgos. 3. Usar cortex.ref para consultar plantillas y formatos CORTEX. 4. Procesar toda la informacion. Completar 18 secciones via blueprint.synthesize(bp_id, content) en 1 llamada. 5. Verificar coherencia transversal: §2 ↔ §6 ↔ §12 ↔ §11. 6. Presentar BLP completo al Arquitecto para revision holistica. 7. Si el Arquitecto pide revision externa: cortex.render(bp_id) → HCORTEX. 8. Si hay cambios: blueprint.synthesize(bp_id, content) sobre secciones especificas. 9. Arquitecto conforme → blueprint.ready().", reason:"Diseno conversacional reemplaza 23 llamadas por 4." }


$7: WORKFLOW STEPS — EXECUTION

WRK:w08_execution{ status:"current", owner:"executor", survive:"yes", action:"ejecutar tareas de BLP", procedure:"0. AXM:workflow_fidelity — Cada paso en orden, sin saltos. 1. Executor: blueprint.claim(BLP-NNN) → state = in_progress. 2. Executor lee BLP completo (18 secciones sintetizadas). 3. For EACH task: execute, blueprint.task(completed), checkpoint, next task. 4. On obstacle: blueprint.fail(BLP-NNN, reason). 5. To cancel: blueprint.cancel(BLP-NNN, reason). 6. When ALL tasks done: blueprint.complete(BLP-NNN, evidence) → state = review.", reason:"Ejecucion task-by-task con checkpoint.", checkpoint_rule:"Cada tarea = task.complete() + checkpoint. Nunca 2 sin checkpoint." }


$8: WORKFLOW STEPS — VERIFICATION

WRK:w08_verify{ status:"current", owner:"auditor", survive:"yes", action:"verificar ACs", procedure:"1. Auditor carga BLP + evidence. 2. For each AC: blueprint.ac(verified). Si fail → re_delegate (max 3). 3. 3ra falla → blueprint.block_for_architect(). 4. All ACs pass → blueprint.approve(BLP-NNN) → done.", reason:"Cross-verification de criterios de aceptacion." }


$9: WORKFLOW STEPS — CLOSURE

WRK:w08_closure{ status:"current", owner:"governor", survive:"yes", action:"cerrar ciclo y aprender", procedure:"1. Todos los BLPs del ciclo done/cancelled → cycle.close(). 2. cycle.close auto-genera LESSONS. 3. cortex.learn escanea patrones del ciclo. 4. Candidatos LNG→KNW propuestos al Arquitecto.", reason:"Cierre de ciclo con learning synthesis." }


$10: HANDLERS REEMPLAZADOS EN FASE DE DISENO (w08 v2.0)

LNG:w08_replaced_in_design{ note:"Estos handlers ya NO se usan en la fase de DISENO/SINTESIS (reemplazados por blueprint.synthesize). SIGUEN activos en las fases de EJECUCION y VERIFICACION.", blueprint.create: "Reemplazado por synthesize (creacion atomica dentro del handler)", blueprint.define: "Reemplazado por synthesize (secciones en 1 llamada)", blueprint.update: "Reemplazado por synthesize (parcheo idempotente)", blueprint.mature: "La maduracion es la conversacion con el Arquitecto", blueprint.gate: "Compuertas verificadas durante la conversacion de diseno", blueprint.assign: "El executor se define en la conversacion de diseno" }

AXM:w08_design_vs_exec{ Los handlers blueprint.claim, blueprint.complete, blueprint.fail, blueprint.cancel, blueprint.ac, blueprint.approve, blueprint.re_delegate, y blueprint.block_for_architect SIGUEN activos en las fases de EJECUCION (§7) y VERIFICACION (§8). NO fueron eliminados — solo se excluyen de la fase de DISENO donde synthesize los reemplaza. }


$11: COMPARATIVA 23→4 LLAMADAS

LNG:w08_comparativa{ resumen:"Reduccion de ~23 a ~4 llamadas MCP (83%)", llamadas_mcp_antes:"~23", llamadas_mcp_despues:"~4", reduccion_llamadas:"83%", interacciones_antes:"6+", interacciones_despues:"3", reduccion_interacciones:"50%+", handlers_antes:"20", handlers_despues:"4", reduccion_handlers:"80%", handler_principal_antes:"blueprint.update x18", handler_principal_despues:"blueprint.synthesize x1" }


$12: NOTAS

LNG:w08_notas{ nota1:"Los pasos 1-3 (contexto) usan workflows w01-w02-w03. No cambian.", nota2:"blueprint.synthesize es el corazon del flujo: reemplaza 18+ llamadas por 1.", nota3:"cortex.ref permite al agente consultar plantillas durante la conversacion.", nota4:"La revision externa usa cortex.render (existente). No requiere handler nuevo.", nota5:"No hay stakeholders externos. Solo Arquitecto + agente.", nota6:"Sintesis idempotente: multiples llamadas a synthesize pueden parchear secciones." }
