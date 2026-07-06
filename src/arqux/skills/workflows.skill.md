$0

# -- $0: WORKFLOWS SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# WRK   | work       | attrs      | B | Working        | Workflow result
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram


$1: WORKSPACE INIT

IDN:workflow_init{ name:"Workspace Initialization", purpose:"Setup a new workspace from scratch with full governance.", trigger:"arqux init or workspace.init()" }

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
G --> A: STANDBY — ¿Qué necesita el Arquitecto?
@enduml
}

STP:w01_s{ 1:"Arquitecto solicita inicializar workspace", 2:"workspace.init(path=...)", 3:"Crea .arqux/ con manifest, identities, skills", 4:"Escribe AGENTS.md en raiz del workspace", 5:"Agente entra en STANDBY" }


$2: GOVERN NEW PROJECT

IDN:workflow_govern{ name:"Govern New Project", purpose:"Bring an existing project under Arqux governance with full context.", trigger:"Arquitecto: 'Gobierna el proyecto X'" }

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
note right: El agente LLM estudia el proyecto

G -> G: Sintetiza brain.cortex en CORTEX
G -> PI2: project.init(name=X, path=./X, seed=<brain>)
PI2 -> MB: DOM:project{name, path, domain, stack}
PI2 --> G: project.init ok brain=seeded

G --> A: Proyecto gobernado. ¿Abro ciclo?
@enduml
}

STP:w02_s{ 1:"project.init(name=X, path=./X) — sin seed", 2:"Recibir STP:build_brain", 3:"Estudiar proyecto (README, AGENTS.md, estructura, stack)", 4:"Sintetizar brain.cortex con FCS, OBJ, KNW, RSK, LNG", 5:"project.init(name=X, path=./X, seed=<brain>)", 6:"Brain poblado + meta-brain actualizado + proyecto registrado" }


$3: DAILY SESSION

IDN:workflow_daily{ name:"Daily Session", purpose:"Standard agent session startup under Arqux.", trigger:"Agent starts in a governed workspace." }

DIAG:w03{
@startuml
actor "Arquitecto" as A
participant "alfred (Agent)" as G
database "brain.cortex" as BC
database "AGENTS.md" as AG

G -> AG: Leer AGENTS.md
note right: STANDBY-FIRST

G -> BC: Cargar FCS, OBJ, KNW, LNG
note right: Carga prioritaria de contexto

G -> G: Cargar identidad alfred.cortex

G --> A: STANDBY — Hola Arquitecto. ¿Qué necesita?
A -> G: Continúa tarea T-002
G -> BC: task.read(T-002)
G -> G: task.update(T-002, note="...")
G --> A: Avance reportado
@enduml
}

STP:w03_s{ 1:"Read AGENTS.md (STANDBY-FIRST)", 2:"Load brain.cortex — FCS, OBJ, KNW, LNG as priority", 3:"Load identity from .arqux/identities/", 4:"Open question to the Architect", 5:"Execute assigned task", 6:"Record evidence via task.update or evidence.record" }


$4: TASK LIFECYCLE

IDN:workflow_task{ name:"Task Lifecycle", purpose:"Full lifecycle of a governed task from creation to completion or failure.", trigger:"Governor creates a task." }

DIAG:w04{
@startuml
actor "Arquitecto" as A
participant "Governor" as GOV
participant "Executor" as EXE
database "brain.cortex" as BC
database "tasks/" as TSK

A -> GOV: Crea tarea X
GOV -> TSK: task.create(obj=..., assignee=alfred)
TSK --> GOV: T-001 creada (status=draft)

GOV -> GOV: task.claim no permitido
note right: LIM: governor NO puede claim

A -> EXE: Ejecuta tarea T-001
EXE -> TSK: task.claim(T-001)
TSK --> EXE: T-001 status=in_progress

EXE -> BC: evidence.record(kind="note", payload="50%")
EXE -> TSK: task.update(T-001, note="Mitad completada")

alt Completado
    EXE -> TSK: task.complete(T-001, evidence="...")
    TSK --> EXE: T-001 status=done
    BC -> BC: AUD:E_NNN en brain PULSE
else Bloqueado
    EXE -> TSK: task.fail(T-001, reason="...")
    TSK --> EXE: T-001 status=blocked
    BC -> BC: AUD:E_NNN con causa
end

EXE --> A: Tarea completada/bloqueada
@enduml
}

STP:w04_s{ 1:"Governor: task.create(obj=..., assignee=...)", 2:"Executor: task.claim(task_id)", 3:"Executor: works on the task", 4:"Executor: task.update(task_id, note=...) periodically", 5:"Executor: evidence.record(kind=note, payload=...) on milestones", 6:"Executor: task.complete(task_id, evidence=...) or task.fail(task_id, reason=...)", 7:"Brain PULSE automatically records evidence" }


$5: IDENTITY EVOLUTION

IDN:workflow_identity{ name:"Identity Evolution", purpose:"Agent evolves its behavioral identity with lessons learned across sessions.", trigger:"Agent learns a significant behavioral lesson." }

DIAG:w05{
@startuml
actor "Arquitecto" as A
participant Agent as G
database ".arqux/identities/alfred.cortex" as ID

A -> G: Señala un error de comportamiento
note right: Ej: "No uses cortex.write para governance"

G -> G: Sintetiza la lección
note right: LNG:l004{type:"process", cause:"cortex.write...", lesson:"Usar project.init(seed=)..."}

G -> ID: identity.record(lesson="...", kind="process", cause="...")
ID --> G: LNG agregado a $5: BEHAVIORAL LESSONS

G --> A: Lección registrada. No volverá a ocurrir.
@enduml
}

STP:w05_s{ 1:"Architect corrects or agent discovers a behavioral lesson", 2:"Synthesize in LNG format: name{type, cause, lesson}", 3:"identity.record(lesson, kind, cause)", 4:"LNG added to .arqux/identities/<agent>.cortex", 5:"Identity evolves permanently" }


$6: PROTOCOL ADOPTION

IDN:workflow_adopt{ name:"Agent Adoption Protocol", purpose:"Onboard a new agent into the workspace with a specific role.", trigger:"A new agent needs to operate under Arqux." }

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
NA --> A: Listo. ¿Qué necesita el Arquitecto?
@enduml
}
