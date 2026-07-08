$0

# -- $0: WORKFLOW W08 --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit

IDN:w08{ name:"Blueprint Lifecycle", purpose:"Complete lifecycle: triage → indagacion → sintesis autonoma → ready → ejecucion → verificacion → cierre." }

DIAG:w08{
@startuml
title Blueprint Lifecycle — State Machine

state "draft" as D
state "maturing" as M
state "ready" as R
state "in_progress" as IP
state "review" as RV
state "done" as DN
state "blocked" as B
state "cancelled" as CN

[*] --> D : blueprint.create
D --> M : blueprint.mature (indagacion + sintesis)
M --> R : blueprint.ready
R --> IP : claim
IP --> RV : complete
IP --> B : fail
B --> D : re-plan
B --> CN : cancel
RV --> DN : approve
RV --> IP : re-delegate (max 3)
RV --> CN : 3rd fail
@enduml
}


$8.1: CREATION Y SINTESIS — indagacion contextual + sintesis autonoma

AXM:template_is_map{ El BLP template de 18 secciones es el MAPA del diseno. El agente no recorre las secciones con el Arquitecto — las sintetiza internamente tras la conversacion. }

AXM:synthesize_not_iterate{ El agente no pide aprobacion seccion-por-seccion. Tras la indagacion, completa las 18 secciones en un unico lote coherente y presenta el BLP completo al Arquitecto para revision holistica. }

AXM:coherence_check{ La sintesis debe ser coherente transversalmente: objetivo (§2), alcance (§6), criterios de aceptacion (§12) y procedimiento (§11) deben estar alineados. El agente verifica esto internamente antes de presentar. }

STP:w08_synthesis{
  1_indagacion:"Escuchar la vision del Arquitecto en lenguaje natural. NO escribir en el BLP aun.",
  2_preguntar:"Formular preguntas de indagacion para completar el mapa: alcance, limites, criterios de exito, riesgos, restricciones. Preguntar solo lo necesario.",
  3_sintetizar:"Procesar toda la informacion y completar las 18 secciones del BLP en un solo lote via blueprint.update(section=N, content=...) para cada una.",
  4_coherencia:"Verificar coherencia transversal: §2 ↔ §6 ↔ §12 ↔ §11. Ajustar si hay contradicciones.",
  5_presentar:"Presentar el BLP completo al Arquitecto para revision holistica.",
  6_ajustar:"Si el Arquitecto solicita cambios, aplicar blueprint.update(section=N) sobre las secciones especificas.",
  7_aprobar:"Una vez conforme: blueprint.gate(gate=all) → blueprint.ready()",
}


$8.2: READY — Desde maturing o draft directo

AXM:no_define{ El handler blueprint.define() NO se utiliza. La sintesis se hace via blueprint.update(). Se va de draft → maturing → ready. }

STP:w08_ready{
  1:"Blueprint en maturing con diseno validado",
  2:"Governor: blueprint.gate(gate=all) → compuertas de calidad",
  3:"Governor: blueprint.ready(BLP-NNN) → state = ready",
  4:"Governor: blueprint.assign(BLP-NNN, executor)",
  5:"Executor: blueprint.claim(BLP-NNN) → state = in_progress",
  key_rule:"Ready significa diseno sintetizado y validado por el Arquitecto.",
}


$8.3: EXECUTION — Task-by-task con checkpoint

STP:w08_execution{
  0:"AXM:workflow_fidelity — Cada paso en orden, sin saltos.",
  1:"Governor: blueprint.assign(BLP-NNN, executor)",
  2:"Executor: blueprint.claim(BLP-NNN) → state = in_progress",
  3:"Executor lee BLP completo (18 secciones sintetizadas)",
  4:"For EACH task: self-check, execute, blueprint.task(completed), sync_brain() checkpoint, verify WRK, then next task",
  5:"On obstacle: blueprint.fail(BLP-NNN, reason)",
  6:"To cancel: blueprint.cancel(BLP-NNN, reason)",
  7:"When ALL tasks checkpointed: blueprint.complete(BLP-NNN, evidence) → state = review",
  checkpoint_rule:"Nunca 2 tareas sin checkpoint. Cada tarea = task() + sync_brain().",
  recovery:"Interrupcion? session.resume() + WRK:current restaura ultimo checkpoint.",
}


$8.4: CROSS-VERIFICATION — AC por AC

STP:w08_verify{
  1:"Auditor carga BLP + evidence",
  2:"For each AC: blueprint.ac(verified). Si fail: blueprint.ac(failed) → re_delegate (max 3)",
  3:"3ra falla → blueprint.block_for_architect()",
  4:"All ACs pass → blueprint.approve(BLP-NNN) → done",
}


$8.5: CLOSURE — Learning synthesis

STP:w08_closure{
  1:"When all Blueprints in cycle are done/cancelled: cycle.close()",
  2:"cycle.close auto-generates LESSONS",
  3:"cortex.learn scans cycle for patterns",
  4:"Elevation candidates (LNG→KNW) proposed for Architect review",
}
