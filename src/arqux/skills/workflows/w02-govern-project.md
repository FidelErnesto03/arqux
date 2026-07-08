$0

# -- $0: WORKFLOW W02 —
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram

IDN:w02{ name:"Govern New Project", purpose:"Bring an existing project under Arqux governance with full context.", trigger:"Arquitecto: 'Gobierna el proyecto X'" }

DIAG:w02{
@startuml
actor "Arquitecto" as A
participant Agent as G
participant "project.init (sin seed)" as PI1
participant "Proyecto (files)" as PRJ
participant "project.init (con seed)" as PI2
database "meta-brain.cortex" as MB

A -> G: Gobierna el proyecto X
G -> PI1: project.init(name=X, path=./X)
PI1 --> G: STP:build_brain instructions

G -> PRJ: Leer README, AGENTS.md, estructura
G -> PRJ: Identificar stack, dominio, riesgos
note right: LLM agent studies the project

G -> G: Synthesizes brain.cortex in CORTEX
G -> PI2: project.init(name=X, path=./X, seed=<brain>)
PI2 -> MB: DOM:project{name, path, domain, stack}
PI2 --> G: project.init ok brain=seeded

G --> A: Project governed. Open cycle?
@enduml
}

STP:w02_s{ 1:"project.init(name=X, path=./X) — sin seed", 2:"Recibir STP:build_brain", 3:"Estudiar proyecto (README, AGENTS.md, estructura, stack)", 4:"Sintetizar brain.cortex con FCS, OBJ, KNW, RSK, LNG", 5:"project.init(name=X, path=./X, seed=<brain>)", 6:"Brain poblado + meta-brain actualizado + proyecto registrado" }
