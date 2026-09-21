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
participant "project.init" as PI
participant "Proyecto (files)" as PRJ
database "projects.cortex\n(workspace index)" as PC
database "meta-brain.cortex" as MB

A -> G: Gobierna el proyecto X
G -> PI: project.init(name=X, path=./X)
note right: BLP-007: sin seed escribe brain\nstarter VALIDATOR-CLEAN\n(templates/brain.cortex)
PI -> PC: upsert DOM:<name>{name,path,domain,status}
PI --> G: project.init ok + registered_in_workspace\n+ STP:build_brain guidance

G -> PRJ: Leer README, AGENTS.md, estructura
G -> PRJ: Identificar stack, dominio, riesgos
note right: LLM agent studies the project

opt seed enriquecido
  G -> G: Synthesizes brain.cortex in CORTEX (validator-required fields)
  G -> PI: project.init(name=X, path=./X, seed=<brain>)
  PI -> MB: cross-project knowledge
  PI --> G: project.init ok brain=seeded
end

G --> A: Project governed. Open cycle?
@enduml
}

STP:w02_s{ 1:"project.init(name=X, path=./X) — escribe brain starter validator-clean (templates/brain.cortex) y registra DOM:<name> en projects.cortex del workspace", 2:"Recibir STP:build_brain guidance + registered_in_workspace", 3:"Estudiar proyecto (README, AGENTS.md, estructura, stack)", 4:"Opcional: sintetizar brain.cortex enriquecido con FCS, OBJ, KNW, RSK, LNG (campos requeridos del validador)", 5:"project.init(name=X, path=./X, seed=<brain>) si aplica", 6:"Brain poblado + proyecto registrado en workspace" }
