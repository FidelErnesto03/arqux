$0

# -- $0: WORKFLOW W01 —
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram

IDN:w01{ name:"Workspace Initialization", purpose:"Setup a new workspace from scratch with full governance.", trigger:"arqux init or workspace.init()" }

DIAG:w01{
@startuml
actor "Arquitecto" as A
participant Agent as G
participant "workspace.init" as WI
database ".arqux/" as FS

A -> G: Iniciar workspace
G -> WI: workspace.init(path=./workspace)
WI -> FS: Crear .arqux/manifest.cortex
WI -> FS: Copiar identidades a .arqux/identities/
WI -> FS: Copiar skills a .arqux/skills/
WI -> FS: Escribir AGENTS.md en raiz
WI --> G: workspace.init ok
G --> A: STANDBY — What does the Architect need?
@enduml
}

STP:w01_s{ 1:"Arquitecto solicita inicializar workspace", 2:"workspace.init(path=...)", 3:"Crea .arqux/ con manifest, identities, skills", 4:"Escribe AGENTS.md en raiz del workspace", 5:"Agente entra en STANDBY" }
