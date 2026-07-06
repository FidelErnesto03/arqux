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
G --> A: STANDBY — What does the Architect need?
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
note right: LLM agent studies the project

G -> G: Synthesizes brain.cortex in CORTEX
G -> PI2: project.init(name=X, path=./X, seed=<brain>)
PI2 -> MB: DOM:project{name, path, domain, stack}
PI2 --> G: project.init ok brain=seeded

G --> A: Project governed. Open cycle?
@enduml
}

STP:w02_s{ 1:"project.init(name=X, path=./X) — sin seed", 2:"Recibir STP:build_brain", 3:"Estudiar proyecto (README, AGENTS.md, estructura, stack)", 4:"Sintetizar brain.cortex con FCS, OBJ, KNW, RSK, LNG", 5:"project.init(name=X, path=./X, seed=<brain>)", 6:"Brain poblado + meta-brain actualizado + proyecto registrado" }


$3: SESSION START — CONTEXT RESPONSE

IDN:workflow_session{ name:"Session Start", purpose:"Agent startup in a governed workspace. Presents context from brain.cortex at the appropriate level. Replaces the old Daily Session workflow.", trigger:"Agent starts in a governed workspace." }

AXM:session_context_first{ The FIRST response in a governed workspace MUST include context from brain.cortex. The response level depends on where the agent is in the workspace tree. }

DIAG:w03{
@startuml
actor "Arquitecto" as A
participant Agent as G
database "brain.cortex" as BC
database "AGENTS.md" as AG

G -> AG: Read AGENTS.md
note right: PHASE 0: detect .arqux/

G -> G: Verify ARQUX_AGENT_ROLE
note right: Must be governor for write access

alt Workspace root (no project selected)
    G -> BC: Read meta-brain.cortex
    G --> A: List projects with status + description
else Inside a project
    G -> BC: Read brain.cortex (FCS, OBJ, LNG)
    G --> A: Project + cycle + blueprints status
else Inside a cycle
    G -> BC: Read cycle MANIFEST.md
    G --> A: Cycle manifest + all blueprints with status
end

G --> A: Open question — what to work on?
@enduml
}

STP:w03_s{
  1:"Verify ARQUX_AGENT_ROLE — report if auditor/empty",
  2_workspace_level:"List projects from meta-brain: name, last active, status. Ask which to work on.",
  3_project_level:"Read brain.cortex: project, active cycle, blueprints (count + status). Present in HCORTEX.",
  4_cycle_level:"Read MANIFEST.md: objectives, blueprints with status, next control point.",
  5_format:"HCORTEX vertical layout with one-line summary + open question.",
  key_rule:"Context before conversation. Never just a greeting.",
}


$4: TASK LIFECYCLE (LEGACY — PREFER BLUEPRINTS)

IDN:workflow_task{ name:"Task Lifecycle", purpose:"Legacy task workflow. Tasks are simple work items within a cycle. For complex, design-driven work, use Blueprints (w08) which provide 18-section specifications, quality gates, maturation, and cross-verification. Tasks are still supported for quick, low-complexity items that don't need full Blueprint governance.", trigger:"Governor creates a simple task that doesn't need a Blueprint." }

AXM:tasks_vs_blueprints{ Tasks are for simple work items (quick fixes, notes, minor changes). Blueprints (w08) are for governed work items that require design, maturation, and cross-verification. If in doubt, use a Blueprint. }

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
NA --> A: Ready. What does the Architect need?
@enduml
}


$7: SKILL LIFECYCLE

IDN:workflow_skill{ name:"Skill Lifecycle", purpose:"Acquire, install, convert to CORTEX, use, adapt, and evolve external skills under Arqux governance.", trigger:"Architect wants to use an external skill (marketplace, platform, third-party)" }

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


$8: BLUEPRINT WORKFLOW

IDN:workflow_blueprint{ name:"Blueprint Lifecycle", purpose:"Complete lifecycle: cycle maturation → Blueprint creation → maturation → execution → cross-verification → learning." }

DIAG:w08{
@startuml
title Blueprint Lifecycle — Maturation + Execution

state "draft" as D
state "defined" as DF
state "maturing" as M
state "ready" as R
state "in_progress" as IP
state "review" as RV
state "done" as DN
state "blocked" as B
state "cancelled" as CN

[*] --> D : blueprint.create (pre-filled from brain)
D --> DF : blueprint.define
DF --> M : blueprint.mature
M --> M : cyclic interaction (agent ↔ architect)
M --> R : architect: ready
R --> IP : claim
IP --> RV : complete
IP --> B : fail
B --> M : re-plan
B --> CN : cancel
RV --> DN : approve
RV --> IP : re-delegate (max 3)
RV --> CN : 3rd fail
@enduml
}


$8.1: CREATION — blueprint.create

AXM:create_not_for_review{ The DRAFT created by blueprint.create is NOT ready for Architect review. It is a skeleton with brain context pre-filled. The agent MUST immediately call blueprint.define() to fill all sections before presenting to the Architect. }

STP:w08_create{
  1:"Architect states a need: 'Implement OAuth2 token endpoint'",
  2:"Governor: blueprint.create(obj='OAuth2 token endpoint', cycle='CYCLE-01')",
  3:"BLP_TEMPLATE.md is copied → BLP-NNN.md in draft state",
  4:"SECTION PRE-FILL (automatic): context from brain.cortex and cycle MANIFEST.md",
  5:"IMMEDIATELY AFTER: call blueprint.define() to fill ALL remaining sections.",
  "   The draft has brain context but is INCOMPLETE.",
  "   Architect expects: §3 Preconditions, §6 Scope, §8 PUML, §9 PUML, §11 Procedure, §12 AC, §14 Tasks.",
  6:"ONLY after define() is complete, proceed to maturation.",
  key_rule:"NEVER present a draft to the Architect. Always define first, then mature."
}


$8.2: DEFINITION — blueprint.define

STP:w08_define{
  1:"Governor fills remaining sections based on Architect's initial feedback:",
  "   §6 Scope & Exclusions",
  "   §12 Acceptance Criteria (2+ ACs with verification)",
  "   §11 Work Procedure (phases + rollback)",
  "   §13 Required Validations",
  "   §8 Technical Design (PUML component diagram)",
  "   §9 Operational Design (PUML sequence diagram)",
  "   §5 Context (PUML deployment diagram)",
  "   §14 Tasks (T-1.1, T-1.2... breakdown)",
  "   §16 Blocking Rule",
  2:"blueprint.define(BLP-NNN, pre=[...], scope='...', ac=[...], ...)",
  3:"State → defined"
}


$8.3: MATURATION — Cyclic Architect Interaction

AXM:maturation{ Maturation is a CYCLIC dialogue between agent and Architect. It is NOT automatic. The agent proposes refinements. The Architect reviews, approves, or requests changes. This repeats until the Architect is fully satisfied. }

STP:w08_mature{
  1:"Governor: blueprint.mature(BLP-NNN) → state = maturing",
  2:"AGENT reviews the 6 Quality Contract gates (§18):",
  "   has_clear_objective | has_verifiable_preconditions | has_scope_and_exclusions",
  "   has_acceptance_criteria | has_work_procedure | has_required_validations",
  3:"AGENT identifies weak or incomplete gates",
  4:"AGENT presents to Architect in natural language:",
  "   'Arquitecto, BLP-001 tiene §11 Procedure débil (falta rollback).",
  "    También §12 AC-01 no tiene comando de verificación.",
  "    Propongo: agregar fase de rollback y comando pytest.'",
  5:"ARCHITECT responds:",
  "   a) 'Aprobado' → agent applies changes → repeats from step 2",
  "   b) 'Ajusta X, cambia Y' → agent adjusts per feedback → repeats from step 3",
  "   c) 'Ready' → agent calls blueprint.ready(BLP-NNN) → state = ready",
  6:"blueprint.ready() marks the Blueprint as executable. Governor can assign executor.",
  note:"The maturation loop has NO maximum. It ends only when the Architect declares 'ready'.",
  key_rule:"The Architect is the final authority on readiness. The 6 gates guide the agent, they do NOT replace human judgment."
}


$8.4: EXECUTION — Task-by-task usando blueprint.task

STP:w08_execution{
   1:"Governor: blueprint.assign(BLP-NNN, executor='jarvis')",
   2:"Executor: blueprint.claim(BLP-NNN) → state = in_progress",
   3:"Executor reads full BLP-NNN.md: §8 Technical Design, §9 Operational Design, §11 Procedure, §14 Tasks",
   4:"For EACH task in §14 (T-1.1, T-1.2...):",
   "   a) Self-check: 'Can I complete this with my current tools and knowledge?'",
   "   b) If NO → escalate to governor/architect immediately",
   "   c) If YES → execute following the procedure",
   "   d) blueprint.task(bp_id, task_id='T-1.1', status='in_progress', evidence='Started task')",
   "   e) Execute the work and record evidence: evidence.record(kind='artifact', payload=...)",
   "   f) blueprint.task(bp_id, task_id='T-1.1', status='completed', evidence='Task done with result X')",
   5:"On obstacle: blueprint.fail(BLP-NNN, reason='...') → governor re-evaluates",
   6:"To cancel: blueprint.cancel(BLP-NNN, reason='...') → state = cancelled (governor-only)",
   7:"When all tasks complete: blueprint.complete(BLP-NNN, evidence='...') → state = review",
   key_rule:"Executor NEVER modifies the design. Design change → ask Architect."
}


$8.5: CROSS-VERIFICATION — AC por AC con re-delegacion automatica

STP:w08_verify{
   1:"Auditor loads BLP-NNN.md + evidence from execution",
   2:"Cross-compare results against design using blueprint.ac:",
   "   For EACH AC in §12 (AC-01, AC-02...):",
   "   a) blueprint.ac(bp_id, ac_id='AC-01', status='verified', evidence='...') → [x]",
   "   b) If any AC fails: blueprint.ac(bp_id, ac_id='AC-01', status='failed', reason='...')",
   "      → AUTO re-delegate: blueprint.re_delegate()",
   "      → Blueprint returns to in_progress automatically",
   "   Also verify: §13 Required Validations (commands, tests) and §8 Technical Design match",
   3:"Re-delegation loop (MAX 3 via MAX_VERIFICATION_LOOPS):",
   "   Attempt 1-2: blueprint.ac fail → auto re_delegate → executor retries",
   "   Attempt 3: blueprint.ac fail → max loops → instruction to call blueprint.block_for_architect()",
   "   → Architect manually reviews and decides: fix, cancel, or new Blueprint",
   4:"When all ACs pass: blueprint.approve(BLP-NNN) → state = done",
   5:"On approve: identity.record(lesson='BLP-NNN design verified', kind='process')",
   key_rule:"3rd failure is NOT silent — it goes directly to the Architect."
}


$8.6: CLOSURE — Learning synthesis

STP:w08_closure{
  1:"When all Blueprints in cycle are done or cancelled: cycle.close()",
  2:"cycle.close auto-generates LESSONS from all Blueprints",
  3:"cortex.learn scans the cycle for patterns across Blueprints",
  4:"Elevation candidates (LNG→KNW) proposed for Architect review",
  key_rule:"Every closed cycle feeds the brain. Knowledge compounds over time."
}
