$0

# -- $0: WORKFLOW W04 —
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule

IDN:w04{ name:"Reactive Work — Task Lifecycle", purpose:"For urgent/reactive work: incident response, diagnostics, emergency fixes, monitoring. No pre-design — direct execution with full traceability.", trigger:"An incident, outage, or urgent diagnostic requires immediate action." }

AXM:decision_matrix{
  use_tasks_when:"Incident response, emergency fixes, diagnostics, monitoring, hotfixes, security patches. The work is reactive — there was no time for pre-design.",
  use_blueprints_when:"Planned features, architectural changes, new components, refactoring, system design. The work has a pre-design phase and benefits from cyclic maturation with the Architect.",
  rule_of_thumb:"If the Architect says 'resuelve esto YA', use Tasks. If the Architect says 'diseñemos X', use Blueprints.",
}

AXM:task_rigor{ Even urgent tasks MUST include: objective, preconditions, acceptance criteria, blockers, evidence per action, and lessons learned. Speed does not excuse lack of traceability. }

DIAG:w04{
@startuml
actor Arquitecto
participant Agent
database "tasks/" as TSK

Arquitecto -> Agent: Incidente/urgencia
Agent -> Agent: Evaluar: ¿requiere diseño previo?
note right: Si NO → Tasks
Agent -> TSK: task.create(obj, priority=high)
TSK --> Agent: T-001 (draft)

Agent -> TSK: task.claim(T-001)
Agent -> TSK: task.update(T-001, note="in progress")
note right: Ejecucion directa

loop Cada accion
  Agent -> TSK: evidence.record(kind=artifact)
end

Agent -> TSK: task.complete(T-001, evidence)
Agent -> Agent: identity.record(lessons)
Agent --> Arquitecto: Diagnostico + handoff
@enduml
}

STP:w04_s{
  1:"Architect reports incident or urgent request",
  2:"Agent evaluates: ¿requires pre-design? If NO → use Tasks",
  3:"task.create(obj, priority=high) — includes blockers and ACs",
  4:"task.claim and execute directly — no maturation phase needed",
  5:"evidence.record for every action taken",
  6:"task.complete with full evidence and lessons",
  7:"identity.record with lessons learned",
  handoff:"Task completed → handoff to Architect with monitoring plan if needed",
}
