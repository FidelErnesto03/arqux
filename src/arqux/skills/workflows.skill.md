$0

# -- $0: WORKFLOWS SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable principle

IDN:workflows{ name:"Workflows Library Index", purpose:"Index of canonical workflows. Load individual workflows from workflows/ subdirectory.", path:".arqux/skills/workflows/" }

AXM:triage_before_create{ No llamar blueprint.create() sin pasar por STP:triage primero. Triage decide si la solicitud merece BLP (w08) o es tarea puntual (w04). }

AXM:analysis_confinement{ Durante modo design (analisis consultivo), toda sugerencia del Arquitecto se DOCUMENTA en la seccion correspondiente del template BLP. NO se ejecuta hasta modo exec. Excepcion: si el Arquitecto dice explicitamente "hazlo ahora". }

AXM:template_is_map{ El BLP template de 18 secciones es el MAPA de la conversacion de diseno. El agente camina las secciones con el Arquitecto. Cada respuesta del Arquitecto ES contenido de esa seccion. Al terminar la conversacion, el BLP esta sustancialmente completo. }

AXM:mode_aware{ El agente opera segun el FCS:mode actual: design = documentar sugerencias en secciones sin ejecutar; exec = ejecutar tareas con checkpoint; review = verificar ACs; triage = decidir ruta. }


$1: TRIAGE — Pre-workflow decision

STP:triage{ 0:"Al recibir solicitud: NO crear BLP aun", 1:"Preguntar: requiere diseno (ACs, diagramas, reglas)?", 2:"SI -> es Blueprint -> analisis consultivo guiado por template -> define() -> ready()", 3:"NO -> es tarea -> w04 tarea urgente", key_rule:"Si al terminar analisis el diseno no esta claro, falta conversacion." }


$2: WORKFLOW INDEX

IDN:w01{ name:"Workspace Initialization", file:"workflows/w01-workspace-init.md", purpose:"Setup a new workspace from scratch with full governance.", trigger:"arqux init or workspace.init()" }

IDN:w02{ name:"Govern New Project", file:"workflows/w02-govern-project.md", purpose:"Bring an existing project under Arqux governance with full context.", trigger:"Arquitecto: 'Gobierna el proyecto X'" }

IDN:w03{ name:"Session Start", file:"workflows/w03-session-start.md", purpose:"Agent startup in a governed workspace. Presents context from brain.cortex.", trigger:"Agent starts in a governed workspace." }

IDN:w04{ name:"Reactive Work — Task Lifecycle", file:"workflows/w04-reactive-task.md", purpose:"For urgent/reactive work: incident response, diagnostics, emergency fixes.", trigger:"An incident, outage, or urgent diagnostic." }

IDN:w05{ name:"Identity Evolution", file:"workflows/w05-identity-evolution.md", purpose:"Agent evolves its behavioral identity with lessons learned.", trigger:"Agent learns a significant behavioral lesson." }

IDN:w06{ name:"Agent Adoption Protocol", file:"workflows/w06-agent-adoption.md", purpose:"Onboard a new agent into the workspace with a specific role.", trigger:"A new agent needs to operate under Arqux." }

IDN:w07{ name:"Skill Lifecycle", file:"workflows/w07-skill-lifecycle.md", purpose:"Acquire, install, convert, use, adapt, and evolve external skills.", trigger:"Architect wants to use an external skill." }

IDN:w08{ name:"Blueprint Lifecycle", file:"workflows/w08-blueprint-lifecycle.md", purpose:"Complete lifecycle: triage -> analisis consultivo -> definicion -> ready -> ejecucion -> verificacion -> cierre.", trigger:"A new feature, component, or refactor requiring design." }

IDN:w09{ name:"CRUD Write Blocked", file:"workflows/w09-crud-blocked.md", purpose:"Diagnose and resolve E032/E034 non-bypassable validation errors on brain writes.", trigger:"E015_ATOMIC_WRITE_FAILED con errores E032/E034." }
IDN:w10{ name:"Identity Handoff", file:"workflows/w10-identity-handoff.md", purpose:"Detect agent identity from greeting and enable hot handoff between identities.", trigger:"Arquitecto saluda con nombre de agente o solicita handoff." }
IDN:w11{ name:"Cortex File Repair — Backup & Rewrite", file:"workflows/w11-cortex-file-repair.md", purpose:"Repair .cortex files with blocking validation errors (E032/E034/E008) using BLP-042 backup→rewrite protocol.", trigger:"cortex verify --strict reveals blocking errors, or w09 auto-repair fails repeatedly." }