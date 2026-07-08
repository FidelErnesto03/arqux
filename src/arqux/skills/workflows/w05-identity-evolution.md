$0

# -- $0: WORKFLOW W05 —
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram

IDN:w05{ name:"Identity Evolution", purpose:"Agent evolves its behavioral identity with lessons learned across sessions.", trigger:"Agent learns a significant behavioral lesson." }

DIAG:w05{
@startuml
actor "Arquitecto" as A
participant Agent as G
database ".arqux/identities/alfred.cortex" as ID

A -> G: Points out a behavioral error
note right: Eg: "Do not use cortex.write for governance"

G -> G: Synthesizes the lesson
note right: LNG:l004{type:"process", cause:"cortex.write...", lesson:"Usar project.init(seed=)..."}

G -> ID: identity.record(lesson="...", kind="process", cause="...")
ID --> G: LNG added to $5: BEHAVIORAL LESSONS

G --> A: Lesson registered. It will not happen again.
@enduml
}

STP:w05_s{ 1:"Architect corrects or agent discovers a behavioral lesson", 2:"Synthesize in LNG format: name{type, cause, lesson}", 3:"identity.record(lesson, kind, cause)", 4:"LNG added to .arqux/identities/<agent>.cortex", 5:"Identity evolves permanently" }
