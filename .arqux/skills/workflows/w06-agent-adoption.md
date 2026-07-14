$0

# -- $0: WORKFLOW W06 --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule

IDN:w06{ name:"Agent Adoption Protocol", purpose:"Onboard a new agent into the workspace with a specific role via protocol.onboard (meta-handler: 2→1 calls, 50% reduction).", trigger:"A new agent needs to operate under Arqux.", handler:"protocol.onboard" }

DIAG:w06{
@startuml
title w06 — Agent Adoption (Optimizado: protocol.onboard)

actor "Arquitecto" as A
participant "Agente (alfred)" as G
participant "MCP Server" as S
participant "Handler: protocol.onboard" as H
database "identity.cortex" as ID

A -> G: Da de alta a Y como executor
G -> S: protocol.onboard(agent_id="Y", role="executor")
S -> H: dispatch protocol.onboard
note right: Agrupa: cortex.read(identity, mode=native)\n+ protocol.adopt
H -> ID: Lee identidad Y (mode=native)
ID --> H: CORTEX source nativo
H -> H: Adopta agente Y como executor
H --> S: ok (Y adoptado como executor)
S --> G: Y adoptado como executor
G --> A: Y ya puede operar
@enduml
}

AXM:w06_single_call{ protocol.onboard agrupa 2 llamadas atomicas (cortex.read + protocol.adopt) en 1 sola llamada. Reduccion: 50%. }

# HANDLER: protocol.onboard — Onboard an agent: reads identity + adopts in 1 call (BLP-003 meta-handler). Replaces cortex.read + protocol.adopt (2→1).
# NOTA: La lectura de AGENTS.md la hace el agente directamente (archivo, no handler MCP).
# NOTA: protocol.pause, protocol.release, protocol.resume son handlers complementarios (no obligatorios en w06).

STP:w06_onboard{
  1:"Agente detecta .arqux/ leyendo AGENTS.md",
  2:"Agente notifica al Arquitecto — STANDBY",
  3:"Arquitecto ordena adopcion con rol",
  4:"Governor ejecuta protocol.onboard(agent_id, role) — 1 llamada",
  5:"protocol.onboard internamente: lee identity.cortex + adopta agente",
  6:"Agente asume identidad + rol — listo para operar",
  key_rule:"1 llamada MCP. protocol.onboard wrappea cortex.read + protocol.adopt.",
}
