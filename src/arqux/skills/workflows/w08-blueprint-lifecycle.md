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
title Blueprint Lifecycle — State Machine (BLP-004 simplified, BLP-009 gate)

state "draft" as D
state "ready" as R
state "in_progress" as IP
state "done" as DN
state "blocked" as B
state "cancelled" as CN

[*] --> D : blueprint.create / synthesize
D --> R : blueprint.ready\n(gate: no template placeholders)
R --> IP : blueprint.claim
IP --> DN : blueprint.complete\n(validates §12 ACs + §14 tasks)
IP --> B : blueprint.fail / block_for_architect
B --> IP : blueprint.re_delegate (reopens)
DN --> IP : blueprint.re_delegate (reopens)
D --> CN : blueprint.cancel
B --> CN : blueprint.cancel
note right of DN : done y cancelled\nson terminales para fail/cancel
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
  7_aprobar:"Una vez conforme: blueprint.ready() → gate de placeholders (BLP-009): OUT-ERROR VALIDATION + pending[] si quedan markers _…_ de la plantilla; §18 ☐/✅ excluido",
}


$8.2: READY — Desde draft directo

AXM:no_define{ El handler blueprint.define() NO se utiliza. La sintesis se hace via blueprint.update(). Se va de draft → ready. }

STP:w08_ready{
  1:"Blueprint en draft con diseno validado y SIN placeholders de plantilla (gate BLP-009: OUT-ERROR code=VALIDATION + pending[] si quedan markers)",
  2:"Governor: blueprint.ready(BLP-NNN) → state = ready (rechazado si hay placeholders pendientes — el status queda draft)",
  3:"Executor: blueprint.claim(BLP-NNN) → state = in_progress + asignacion implicita de executor",
  key_rule:"Ready significa diseno sintetizado, validado por el Arquitecto, y sin placeholders sin llenar.",
}


$8.3: EXECUTION — Task-by-task con checkpoint

STP:w08_execution{
  0:"AXM:workflow_fidelity — Cada paso en orden, sin saltos.",
  1:"Governor: blueprint.claim(BLP-NNN) asigna y reclama",
  2:"Executor: blueprint.claim(BLP-NNN) → state = in_progress",
  3:"Executor lee BLP completo (18 secciones sintetizadas)",
  4:"For EACH task: self-check, execute, blueprint.task(completed), sync_brain() checkpoint, verify WRK, then next task",
  5:"On obstacle: blueprint.fail(BLP-NNN, reason)",
  6:"To cancel: blueprint.cancel(BLP-NNN, reason)",
  7:"When ALL tasks checkpointed: blueprint.complete(BLP-NNN, evidence) → state = done (BLP-004: un solo paso; EXECUTION_INCOMPLETE si quedan tareas/ACs abiertos)",
  checkpoint_rule:"Nunca 2 tareas sin checkpoint. Cada tarea = task() + sync_brain().",
  recovery:"Interrupcion? session.resume() + WRK:current restaura ultimo checkpoint.",
}


$8.4: CROSS-VERIFICATION — AC por AC

STP:w08_verify{
  1:"Executor verifica cada AC durante la ejecucion: blueprint.ac(AC-NN, verified, evidence) marca el checkbox en §12",
  2:"Si un AC falla: blueprint.ac(AC-NN, failed, reason) → blueprint.re_delegate (max 3 loops)",
  3:"3ra falla → blueprint.block_for_architect()",
  4:"Con todos los ACs verificados y tareas cerradas: blueprint.complete → done en un paso",
}


$8.5: CLOSURE — Learning synthesis

STP:w08_closure{
  1:"When all Blueprints in cycle are done/cancelled: cycle.close()",
  2:"cycle.close auto-generates LESSONS",
  3:"cortex.learn scans cycle for patterns",
  4:"Elevation candidates (LNG→KNW) proposed for Architect review",
}
