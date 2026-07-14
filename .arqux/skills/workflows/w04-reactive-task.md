$0

# -- $0: WORKFLOW W04 --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# STP   | step       | attrs      | M | Working        | Workflow step

IDN:w04{ name:"Reactive Work — Task Lifecycle", purpose:"For urgent/reactive work: incident response, diagnostics, emergency fixes, monitoring. No pre-design — direct execution with full traceability. task.run marks task complete or fail with evidence and PULSE audit. Task must be created first via task.create.", trigger:"An incident, outage, or urgent diagnostic requires immediate action." }

AXM:decision_matrix{
  use_tasks_when:"Incident response, emergency fixes, diagnostics, monitoring, hotfixes, security patches. The work is reactive — there was no time for pre-design.",
  use_blueprints_when:"Planned features, architectural changes, new components, refactoring, system design. The work has a pre-design phase and benefits from cyclic maturation with the Architect.",
  rule_of_thumb:"If the Architect says 'resuelve esto YA', use Tasks. If the Architect says 'disenemos X', use Blueprints.",
}

AXM:task_rigor{ Even urgent tasks MUST include: objective, preconditions, acceptance criteria, blockers, evidence per action, and lessons learned. Speed does not excuse lack of traceability. }


$1: DIAGRAMA DE SECUENCIA — task.run (6→1 llamadas, 83% reduccion)

DIAG:w04{
@startuml
title w04 — Reactive Task (Optimizado: task.run meta-handler)

actor "Arquitecto" as A
participant "Agente (alfred)" as G
participant "Handler: task.run" as TR
database "tasks/" as TSK
database "pulse.jsonl" as PL
database "identities/" as ID

A -> G: Incidente / urgencia
G -> G: Evalua: requiere diseno previo? (NO -> Tasks)
G -> TR: task.run(obj, priority=high, content, lessons)
note right: 1 llamada reemplaza 6:\ncreate + claim + update +\nevidence + complete +\nidentity.record
TR -> TSK: create + claim + update
TR -> PL: evidence.record (por accion)
TR -> TSK: complete
TR -> ID: identity.record (lesson)
TR --> G: T-001 completada + evidencia + leccion
G --> A: Diagnostico + handoff
@enduml
}


$2: HANDLERS — task.run meta-handler (unico handler requerido)

HDL:w04_handlers{
  handler:"task.run",
  mcp_tool:"task_run",
  description:"Executes a task: marks complete or fail with evidence and PULSE audit. Requires task_id from a previously created task (via task.create).",
  implemented:true,
  notes:"task.create, task.claim, task.update, evidence.record, and task.complete are available as individual handlers for granular control. task.run is the streamlined path for tasks already created."
}


$3: PASOS DEL WORKFLOW

STP:w04_s{
  1:"Architect reports incident or urgent request.",
  2:"Agent evaluates: requires pre-design? If NO → create task via task.create, then execute via task.run.",
  3:"task.create(obj, priority=high) creates the task.",
  4:"task.run(task_id, content) marks the task complete or fail with evidence. Records PULSE audit.",
  5:"Agent reports result to Architect with diagnosis + handoff.",
  handoff:"Task completed → handoff to Architect with monitoring plan if needed."
}


$4: NOTAS Y REGLAS

AXM:task_rigor_note{ Even urgent tasks MUST include: objective, preconditions, ACs, blockers, evidence per action, and lessons learned. Speed does not excuse lack of traceability. }

AXM:atomicos_preservados{ task.create, task.claim, task.update, evidence.record, task.complete, identity.record se preservan como handlers individuales para recovery, checkpoint, y edge cases. task.run es el atajo feliz para el flujo completo. }

AXM:decision_note{ La decision Tasks vs Blueprints la rige AXM decision_matrix. w04 es operativo y ALTERNO a w08: si hay diseno previo -> w08; si es reactivo/urgente -> w04. }
