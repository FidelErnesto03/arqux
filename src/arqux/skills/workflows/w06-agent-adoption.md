$0

# -- $0: WORKFLOW W06 —
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram

IDN:w06{ name:"Agent Adoption Protocol", purpose:"Onboard a new agent into the workspace with a specific role.", trigger:"A new agent needs to operate under Arqux." }

DIAG:w06{
@startuml
actor "Arquitecto" as A
participant "New Agent" as NA
participant "Governor (alfred)" as GOV
database "AGENTS.md" as AG
database "identities/" as ID

A -> NA: Opera bajo Arqux en este workspace
NA -> AG: Leer AGENTS.md
note right: Detecta .arqux/, lee AGENTS.md

NA -> ID: Cargar identidad
NA --> A: STANDBY — Hola Arquitecto

A -> GOV: Adopta al nuevo agente
GOV -> GOV: protocol.adopt(agent_id=newbie, role=executor)
GOV --> A: Nuevo agente adoptado con rol executor

NA -> NA: Asume identidad + rol
NA --> A: Ready. What does the Architect need?
@enduml
}
