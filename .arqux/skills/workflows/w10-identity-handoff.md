$0

# -- $0: WORKFLOW W10 —
# Sigil | Name     | Type       | Risk | Cognitive Layer | Description
# IDN   | identity | attrs      | B    | Semantic        | Workflow definition
# STP   | step     | attrs      | M    | Working         | Workflow step
# HDL   | handler  | attrs-pos  | M    | Semantic        | Handler reference
# DIAG  | diagram  | cuerpo     | B    | Semantic        | PlantUML diagram
# AXM   | axiom    | cuerpo     | H    | Prefrontal      | Non-negotiable rule
# LIM   | limit    | attrs      | M    | Prefrontal      | Hard limit

IDN:w10{ name:"Identity Handoff", purpose:"Detect agent identity from user greeting and enable hot handoff between identities during session.", when:"Architect greets with agent name at session start, or says pasame con X during active session." }

AXM:identity_contract{ La identidad activa define el contrato conductual. Ninguna accion puede ejecutarse si viola los AXM o LIM de la identidad actual. Si el Arquitecto solicita una operacion fuera del alcance, informar impedimento y ofrecer handoff a la identidad competente. }

AXM:header_is_identity{ El header visible (⬡ <AGENTE> | <PROYECTO> | <SCOPE>) debe reflejar SIEMPRE la identidad activa. }

AXM:handoff_handler{ session.handoff(target_agent) lee la sesion actual, serializa a CORTEX, escribe handoff en .arqux/handoffs/<target>.cortex y registra PULSE audit. }

LIM:handoff_while_busy{severity:"warning", limit:"Completar la operacion en curso antes de ejecutar un handoff.", scope:"identity"}


$1: DIAGRAMA — Flujo con session.handoff

DIAG:w10_optimized{
@startuml
title w10 — Identity Handoff (session.handoff)

actor "Arquitecto" as A
participant "Agente" as G
participant "MCP Server" as S
participant "Handler: session.handoff" as H
database "brain.cortex / handoffs/" as BC

== HANDOFF ==
A -> G: Ahora opera como Y
G -> S: session.handoff(target_agent="Y")
S -> H: dispatch session.handoff
H -> BC: Lee sesion actual (read_brain)
H -> BC: Escribe handoffs/Y.cortex
H -> BC: Registra PULSE audit
BC --> H: ok
H --> S: ok (handoff registrado)
S --> G: Handoff a Y completado
G --> A: Ahora opero como Y

== ACCION FUERA DE LIM ==
A -> G: Dame acceso a Z
G -> G: Verifica LIM de Y
G --> A: Y no puede. ¿Handoff a otro agente?
@enduml
}


$2: SALUDO INICIAL — Deteccion de identidad al abrir sesion

STP:w10_saludo{
  1:"Analizar el primer mensaje del Arquitecto en busca de patrones: 'Hola X', 'Hola, soy X'",
  2:"Si se reconoce un nombre de agente conocido (Alfred, Jarvis, Seshat, Heimdall):",
  3:"  Ejecutar session.handoff(target_agent='X') — lee sesion, escribe handoff, registra PULSE",
  4:"  La identidad activa se actualiza",
  5:"Si NO se reconoce nombre: mantener identidad default o del SES previo",
  6:"Si el nombre no corresponde a ningun archivo .cortex: informar e ignorar",
}


$3: HANDOFF EN CALIENTE — Cambio de identidad durante sesion activa

STP:w10_handoff{
  1:"Detectar frases de handoff: 'pasame con X', 'cambia a X', 'switch to X', 'pasa a X', 'llama a X'",
  2:"Verificar que X es un nombre de agente conocido (existe .cortex en .arqux/identities/)",
  3:"Ejecutar session.handoff(target_agent='X') — lee sesion actual, escribe handoff, registra PULSE",
  4:"La identidad activa cambia a X",
  5:"Si X no existe: informar al Arquitecto, ofrecer lista de identidades disponibles",
}


$4: ACCION BLOQUEADA — Rechazo por LIM

STP:w10_bloqueo{
  1:"El Arquitecto solicita una accion",
  2:"Verificar contra los LIM de la identidad activa si la accion esta permitida",
  3:"Si la accion viola un LIM:",
  4:"  Informar que la identidad actual no puede realizar esa accion",
  5:"  Explicar brevemente cual LIM impide la accion",
  6:"  Ofrecer handoff a la identidad competente via session.handoff",
  7:"  Ej: 'Jarvis no puede crear ciclos (LIM:no_create). Quieres que llame a Alfred?'",
  8:"Si la accion esta permitida: ejecutar normalmente",
}


$5: HANDLERS ASOCIADOS

HDL:w10_handlers{
  session.handoff:"Lee sesion actual, serializa a CORTEX, escribe handoffs/<target>.cortex y registra PULSE audit. Param: target_agent. Retorna confirmacion de handoff.",
  session.handoff / dry_run:"Para handoffs de prueba sin modificar estado."
}
