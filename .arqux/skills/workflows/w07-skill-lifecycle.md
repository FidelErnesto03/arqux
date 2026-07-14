$0

# -- $0: WORKFLOW W07 — Skill Lifecycle --
# Sigil | Name   | Type       | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram

IDN:w07{ name:"Skill Lifecycle", purpose:"Acquire, validate, register, and evolve external skills under Arqux governance. skill.install imports raw to originals/, validates $0 header, and registers SKL in brain.cortex.", trigger:"Architect wants to use an external skill." }

DIAG:w07{
@startuml
title w07 — Skill Lifecycle (skill.install)

actor "Arquitecto" as A
participant "Agente (alfred)" as G
participant "MCP Server" as S
participant "Handler: skill.install" as HI
participant "Handler: skill.record" as HR
database "originals/" as OR
database "brain.cortex" as BC

A -> G: Instala skill oracle-apex
G -> S: skill.install(source="marketplace", name="oracle-apex")
S -> HI: dispatch skill.install
HI -> OR: Guarda raw en originals/
HI -> HI: Valida $0 header
HI -> BC: Registra SKL en brain.cortex
HI --> S: ok (skill instalado)
S --> G: oracle-apex listo

A -> G: Registra desviacion del skill
G -> S: skill.record(content="ADA:deviation{...}")
S -> HR: dispatch skill.record
HR --> S: ok (ADA registrada)
S --> G: Desviacion registrada
G --> A: Skill instalado y desviacion documentada
@enduml
}

AXM:w07_install{ skill.install importa raw a originals/, valida estructura, y registra en brain.cortex. No convierte a CORTEX — el skill se usa desde originals/. skill.record acepta content CORTEX nativo para desviaciones. }

STP:w07_s{
  1:"skill.install(source, name) — import + validate + register in brain.cortex",
  2:"skill.list(path) — list available skills",
  3:"Agent loads skill from originals/ or .arqux/skills/",
  4:"Agent executes. If deviation: skill.record(content='ADA:deviation{...}')",
  5:"Periodically: scan adaptations, propose improvements",
  6:"Architect approves → skill.evolve(name, adaptation_id)",
  key_rule:"skill.install importa, valida y registra. No convierte ni escribe CORTEX a .arqux/skills/."
}
