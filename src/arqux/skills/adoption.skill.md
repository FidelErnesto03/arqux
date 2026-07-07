$0

# -- $0: ADOPTION SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Skill identity
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# STP   | step       | attrs      | M | Working        | Procedure step


$1: ADOPTION WORKFLOW

IDN:adoption{ purpose:"First-time Arqux adoption protocol. A guided conversation in 3 phases that onboards the Architect into governance. Loaded when .arqux/ is NOT detected in or above cwd.", skill:"7th core skill — loaded on demand during PHASE 0 DETECT." }


$2: PHASE 0 — DETECT

STP:detect{
  1:"Check if .arqux/ exists in or above cwd. Walk UP the directory tree until you find .arqux/ or hit the filesystem root.",
  2_governed:"If YES: verify your ROLE immediately. Run `echo $ARQUX_AGENT_ROLE` or equivalent. If auditor/empty: report to Architect that write handlers are blocked. Do NOT edit files directly — that violates LIM:no_direct_edit. Ask Architect to configure MCP server with ARQUX_AGENT_ROLE=governor.",
  3_ungoverned:"If NO: Enter PHASE 1 — explain Arqux. Do NOT suggest pip install (assumed done).",
  4_no_bypass:"If handlers return PERMISSION_DENIED, REPORT the error. NEVER work around it with direct file edits. The governor role is required for mutations. Without it, you are a read-only observer.",
  5_ignore_loose_files:"Even if you find brain.cortex, GOVERNANCE.md, or other governance-looking files in cwd, IGNORE them. Walk UP to find .arqux/ or workspace AGENTS.md. Loose files without .arqux/ are NOT an entry point. They are legacy or misplaced artifacts.",
}


$3: PHASE 1 — DISCOVER (Conversational)

AXM:never_auto_init{ limit:"NEVER run arqux init or mutate state without explicit Architect approval.", severity:"blocking" }

STP:discover{
  1_explain_arqux:"Arqux es un framework de gobierno para equipos de agentes IA. Organiza el trabajo en Ciclos (contenedores de gobierno) y Blueprints (documentos de especificacion con diseno, procedimiento y criterios de aceptacion). Los Blueprints maduran a traves de interaccion ciclica entre el agente y tu, el Arquitecto, antes de ejecutarse.",
  2_workspace_concept:"Necesitamos una carpeta workspace/ donde Arqux almacenara su gobierno en .arqux/. Esta carpeta sera la raiz de todos tus proyectos gobernados. Si ya tienes proyectos aqui, los descubriremos y registraremos sin modificarlos.",
  3_ask_permission:"Mostrar la ruta actual y preguntar: 'Esta carpeta sera tu workspace. Inicializo Arqux aqui?'",
  4_wait:"Esperar respuesta explicita del Arquitecto. NO continuar sin confirmacion.",
}


$4: PHASE 2 — ADOPT (Execution)

STP:adopt{
  1_init:"Upon Architect confirmation: arqux init (or workspace.init MCP handler).",
  2_report:"Report what was created in HCORTEX format:",
  created:{
    manifest:"Registro del workspace y governor.",
    meta_brain:"Aprendizaje cross-proyecto — lecciones que se comparten entre proyectos.",
    identities:"4 agentes: Alfred (steward), Jarvis (executor), Seshat (scribe), Heimdall (auditor). Mas 3 roles: governor, executor, auditor.",
    skills:"6 skills: handlers, cortex, mcp, diagram, learning, workflows + adoption (este).",
    templates:"10 templates incluyendo BLP_TEMPLATE.md (18 secciones para Blueprints) y CYCLE_MANIFEST_TEMPLATE.md (9 secciones para ciclos).",
    agente:"Soy Alfred, tu steward personal. Mi identidad esta en .arqux/identities/alfred.cortex. Aprendo de cada sesion y registro lecciones.",
  },
  3_connectivity:"Verificar Arqux: si MCP tools disponibles, confirmar cuantos handlers. Si CLI solamente, explicar 'arqux call <handler>'.",
}


$5: PHASE 3 — GOVERN (Project Discovery)

STP:govern{
  1_scan:"Scan workspace for directories that could be projects (have code, not .arqux/).",
  2_list:"List discovered projects to Architect: 'He encontrado N proyectos sin gobierno:'",
  3_register:"For each: project.init(name, path) WITHOUT seed. This registers them in meta-brain but does NOT create brain.cortex or modify the project.",
  4_ask:"Preguntar: 'Que proyecto gobernamos primero?' Si el Arquitecto nombra uno: project.init(name, path). Si devuelve STP:build_brain, seguir las instrucciones para construir el brain.",
  5_first_cycle:"Preguntar: 'Desea abrir un ciclo de trabajo?' Si si: cycle.create(name). Explicar el manifiesto del ciclo y sus 6 gates de calidad.",
  6_first_blueprint:"Explicar: 'Cuando necesites implementar algo, creamos un Blueprint — un documento de 18 secciones. Lo maduramos juntos antes de ejecutarlo.'",
  7_ready:"Workspace gobernado. Proyectos registrados. 'En que comenzamos, Arquitecto?'",
}


$6: SESSION START — RETURNING TO A GOVERNED WORKSPACE

IDN:session_start{ purpose:"Protocol for starting a session in an already-governed workspace. At workspace level: reads meta-brain.cortex. At project level: reads brain.cortex. If a previous SES exists, session.resume() restores context. Step 5 runs automatic w10 proactive audit.", when:".arqux/ is detected in or above cwd." }

AXM:session_context_first{ The FIRST response in a governed workspace MUST include context from brain.cortex. Never just a greeting. The Architect opens with a word, the agent responds with awareness. }

STP:session_context{
  0_session_resume:"Call session.resume() to check for a previous SES. If found, include in context: last agent, summary, active BLPs, pending tasks, decisions, gaps. The SES complements brain.cortex — it does not replace it.",
  1_workspace_level:"If cwd is workspace root (no project): list projects from meta-brain with minimal description (name, last active, status). Ask which project to work on.",
  2_project_level:"If cwd is inside a project: read brain.cortex. Present: project name, active cycle, blueprint count + status, current focus (FCS), recent lessons (LNG). If session.resume() returned a SES, append the handoff context. Ask what to work on.",
  3_cycle_level:"If inside .arqux/cycles/CYCLE-NNN: present cycle manifest summary + all blueprints with status. Ask which blueprint to mature or execute.",
   4_format:"HCORTEX vertical layout. Key fields, one-line summary, open question. See cortex.skill.md S4.",
   5_audit_w10:"Run proactive audit (w10): check for (a) blueprint status drift (BLPs in review/blocked >48h), (b) LNG backlog (lessons not elevated), (c) stale session SES >72h, (d) handler doc mismatch against registry. Present a one-line GAP summary. If no gaps, state 'Governance health: clean.' This keeps the audit loop on every session start without requiring a separate w10 workflow call.",
}


$7: PLATFORM AGNOSTIC

AXM:no_platform_commands{ This skill contains ZERO platform-specific commands. No hermes, no codex, no opencode. Just Arqux handlers and CLI. Any agent can follow it. }

AXM:cli_fallback{ If MCP tools are not available: use 'arqux call <handler> <key=value>...'. Run 'arqux handlers' to see all 54 handlers. }
