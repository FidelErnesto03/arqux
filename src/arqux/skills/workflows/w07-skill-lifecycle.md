$0

# -- $0: WORKFLOW W07 —
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram

IDN:w07{ name:"Skill Lifecycle", purpose:"Acquire, install, convert to CORTEX, use, adapt, and evolve external skills under Arqux governance.", trigger:"Architect wants to use an external skill (marketplace, platform, third-party)" }

DIAG:w07{
@startuml
actor "Arquitecto" as A
participant Agent as G
participant "originals/" as ORIG
participant ".arqux/skills/" as SK

== ADQUISICION ==
A -> G: Instala skill Oracle APEX
G -> G: Obtiene skill del marketplace
G -> ORIG: Almacena original en skills/originals/
note right: Canon externo preservado

== CONVERSION ==
G -> G: Convierte a CORTEX ultra-denso
G -> SK: Escribe en skills/oracle-apex.skill.md
note right: Unico formato disponible para agentes

== USO ==
G -> SK: Carga skill desde .arqux/skills/
G -> G: Ejecuta siguiendo el skill

== ADAPTACION ==
G -> G: Detecta desviacion del skill
G -> SK: skill.record() → $0: ADAPTATIONS
note right: ADA en el propio skill

== EVOLUCION ==
G -> SK: Acumula ADAs en $0
G -> G: Escanea patrones de ADA en $0
G --> A: Propuesta de mejora
A -> G: Aprobado
G -> SK: Actualiza skill con mejora
@enduml
}

STP:w07_s{ 1:"skill.import(source, name) — acquire skill, store original in originals/", 2:"skill.convert(name) — convert to CORTEX ultra-dense, write to skills/", 3:"Agent loads from .arqux/skills/ (directive: NOT from external)", 4:"Agent executes. If deviation: skill.record(name, expected, actual, reason)", 5:"Periodically: scan adaptations, propose improvements", 6:"Architect approves → skill.evolve(name, adaptation_id)" }
