$0

# -- $0: WORKFLOW W05 — Identity Evolution --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs      | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule

IDN:w05{ name:"Identity Evolution", purpose:"Agent evolves its behavioral identity with lessons learned across sessions. cortex.patch updates entries in .cortex files atomically via crud_update.", trigger:"Agent learns a significant behavioral lesson." }

AXM:w05_patch{ cortex.patch reemplaza el cuerpo de entradas CORTEX por selector. Usa crud_update para modificacion atomica con verificacion y backup. }

DIAG:w05{
@startuml
title w05 — Identity Evolution (cortex.patch)

actor "Arquitecto" as A
participant "Agente" as G
participant "MCP Server" as S
participant "Handler: cortex.patch" as HP
database "identity.cortex" as ID

A -> G: Registra leccion: hacer X por Y
G -> G: Sintetiza leccion en formato LNG
G -> S: cortex.patch(path="identity.cortex", content)
S -> HP: dispatch cortex.patch
HP -> ID: crud_update (reemplaza entrada por selector)
HP -> HP: verify + validate + backup
ID --> HP: ok
HP --> S: ok (entrada actualizada)
S --> G: entradas actualizadas
G --> A: Leccion registrada. No ocurrira de nuevo.
@enduml
}

HDL:w05{
  cortex.patch:"Actualiza el cuerpo de entradas CORTEX por selector via crud_update. Escritura atomica con verificacion y backup."
}

STP:w05_s{
  1:"Architect corrects or agent discovers a behavioral lesson",
  2:"Synthesize lesson in LNG format: name{kind, cause, lesson, prevention}",
  3:"cortex.patch(path=identity_file, content='$SELECTOR:{new_body}') — 1 MCP call",
  4:"cortex.patch atomically replaces entry body via crud_update, verifies, and backs up",
  5:"Identity evolves permanently — lesson stored in identity.cortex",
  key_rule:"cortex.patch usa crud_update para reemplazo atomico de entradas."
}
