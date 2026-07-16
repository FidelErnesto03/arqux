$0

# -- $0: CORTEX SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Concept definition
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# STP   | step       | attrs      | M | Working        | Procedure / instruction
# OUT   | output     | attrs      | M | Working        | CORTEX-OUT example
# FMT   | format     | attrs      | B | Semantic       | Formatting rule


$1: CANONICAL RULES

AXM:format{ All CORTEX content uses canonical format: attrs on a single line, cuerpo as multi-line blocks. This applies to ALL CORTEX files — brain.cortex, task.cortex, identities, agent memory. }

AXM:no_prose_in_state{ Governance state (.cortex files) contains ZERO prose. Everything is sigil-structured. If a thought doesn't fit in sigil form, it doesn't belong in a state file. }

AXM:stable_sigils{ Sigils are stable identifiers. The LLM learns them once and applies them everywhere. New sigils are added at the $0 glossary level. }


$2: NATIVE MEMORY (Agent Memory in CORTEX)

AXM:memory_format{ While operating under Arqux governance, the agent's native memory MUST use CODEC-CORTEX content instead of prose. LNG entries capture lessons in 30 tokens instead of 250 tokens of prose. }

STP:memory_examples{
  lng_lesson:"LNG:l004{type:process, cause:direct_file_edit_broke_format, lesson:Only write_cortex_pair for state files, severity:high, date:2026-06-26}",
  lng_pattern:"LNG:l005{type:infrastructure, cause:test_isolation_failure, lesson:Pytest tmp_path prevents state leakage between handler tests, severity:medium}",
  knw_entry:"KNW:mcp_tools{count:54, modules:[workspace, project, cycle, task, evidence, protocol, cortex, identity, skill, blueprint, setup], protocol:stdio}",
  session:"SES:alfred{input:Arquitecto requests new feature, output:Implemented with evidence, outcome:ok, date:2026-07-04}",
}

AXM:memory_evolves{ Agent memory is a living document. LNG entries accumulate. cortex.learn scans for patterns and proposes elevations to KNW. The agent's knowledge compounds over sessions. }

AXM:one_format_everywhere{ Governance state (.cortex), agent docs (AGENTS.md), skills (.skill.md), output (CORTEX-OUT), and agent memory (memory.md) — ALL use the same sigil format. The LLM learns the language once and applies it everywhere. }


$3: INTERNAL FILES

AXM:internal_cortex{ When the agent creates files for its own use (notes, plans, session records), it SHOULD use CORTEX format. The $0 glossary makes these files self-contained and parseable by any LLM. }

STP:internal_templates{
  plan:"OBJ:plan_name{goal, status, success} STP:step{action, handler} RSK:risk{risk, mitigation}",
  session:"SES:agent{input, output, role, outcome, date} LNG:name{type, context, detail}",
  todo:"WRK:todo{task, status, assignee, cycle, priority} FCS:current{what} OBJ:next{goal}",
}


$4: CORTEX-OUT — OUTPUT PROTOCOL (HCORTEX)

IDN:cortex_out{ purpose:"Token-efficient output protocol for agent responses. Uses HCORTEX formatting: structure over prose, vertical layout, human-readable. The profile is chosen based on interaction TYPE, not which handler was called.", profiles:"MIN (default), WORK, AUDIT, FULL, ERROR" }

AXM:hcortex_output{ CORTEX-OUT uses HCORTEX formatting — human-readable CORTEX. This means: vertical layout with line breaks, indentation for hierarchy, lists, tables, and boxes instead of prose paragraphs, full words (no abbreviations), one-line natural language summary after the structured block. The LLM parses it as efficiently as raw CORTEX. Line breaks are cheap tokens. }

AXM:hcortex_format{ All responses to the Architect use HCORTEX. Vertical tables, lists, PUML diagrams. Full words, no abbreviations. NEVER key=value in plain text. NEVER raw sigils in human-facing messages. }

FMT:hcortex_rules{
  vertical:"Each key-value pair on its own line, indented under the profile header.",
  tables:"Use markdown tables for multi-field comparisons instead of repeated key=value lines.",
  lists:"Use bullet lists for sequences of items instead of comma-separated values.",
  boxes:"Use indented blocks (4 spaces) to group related fields — creates visual hierarchy.",
  full_words:"No abbreviations. 'workspace' not 'ws', 'agent' not 'id', 'cycles' not 'cyc'.",
  summary:"ALWAYS end with a one-line natural language summary after ' — '.",
  diagrams:"When explaining structure or flow, prefer PUML diagram over prose description.",
}

STP:hcortex_good{ patterns:[
  "'⬡ <AGENTE> | <PROYECTO> | <SCOPE>' as first line (see AGENTS.md $2)",
  "Table | Dimension | Value | for key-value pairs",
  "Bullet lists for enumerations",
  "PUML diagrams (@startuml) for flows and states",
  "Running Spanish text for explanations",
]}

STP:hcortex_bad{ patterns:[
  "OUT-WORK key=val,key2=val2",
  "$5/LNG:lesson{type:...} in user-facing messages",
  "key=value pairs without table formatting",
  "Sigils like IDN, FCS, LNG in human text",
  "Response without context header (⬡)",
]}


$4.1: PROFILE SELECTION MATRIX

AXM:profile_selection{ The agent selects the CORTEX-OUT profile based on WHAT the Architect is asking. This is a decision matrix, not a fixed mapping. }

STP:profile_matrix{
  status_query:{
    trigger:"Architect asks: 'contexto?', 'estado?', 'cómo va?', 'qué hay?'",
    profile:"OUT-MIN",
    format:"Key fields only, vertical layout, one-line summary.",
  },
  work_result:{
    trigger:"After completing a handler call: task.complete, cycle.create, blueprint.ready, etc.",
    profile:"OUT-WORK",
    format:"Result fields in vertical layout, key metrics highlighted.",
  },
  analysis_explanation:{
    trigger:"Architect asks: 'explícame', 'analiza', 'por qué', 'cómo funciona', 'explain this codebase'",
    profile:"OUT-AUDIT",
    format:"Structured analysis with sections. Use tables for comparisons, lists for findings, PUML for architecture.",
  },
  full_report:{
    trigger:"Architect asks: 'reporte completo', 'dame todo', 'verbose', 'auditoría'",
    profile:"OUT-FULL",
    format:"Complete state snapshot. All relevant fields. Hierarchical layout.",
  },
  error:{
    trigger:"Any error from handler, permission denied, or operation failure",
    profile:"OUT-ERROR",
    format:"Error code + resolution hint. Always actionable.",
  },
  default:{
    trigger:"Any response not matching above",
    profile:"OUT-MIN",
    format:"Concise vertical layout. Default choice.",
  },
}


$4.2: HCORTEX OUTPUT EXAMPLES

OUT:min_status{
  profile:"OUT-MIN",
  example:"""
OUT-MIN
  workspace:  <your-workspace>
  agent:      alfred
  role:       governor
  cycles:     0
  focus:      none
  — Workspace gobernado, sin ciclos activos.
""",
}

OUT:work_blueprint{
  profile:"OUT-WORK",
  example:"""
OUT-WORK
  blueprint:  BLP-001
  cycle:      CYCLE-01
  status:     ready
  gates:
    ✅ has_clear_objective
    ✅ has_verifiable_preconditions
    ✅ has_scope_and_exclusions
    ✅ has_acceptance_criteria
    ✅ has_work_procedure
    ✅ has_required_validations
  — Blueprint OAuth2 listo para ejecución. 6/6 gates aprobados.
""",
}

OUT:audit_analysis{
  profile:"OUT-AUDIT",
  example:"""
OUT-AUDIT
  topic:      Módulo de pagos
  modules:    4
  pattern:    MVC + Service Layer

  | Capa        | Tecnología      | Responsabilidad          |
  |-------------|-----------------|--------------------------|
  | Controller  | Spring MVC      | Endpoints REST           |
  | Service     | Spring Boot     | Lógica de negocio        |
  | Repository  | JPA/Hibernate   | Acceso a Oracle          |
  | Client      | Feign/RestTmpl  | Comunicación inter-mod   |

  — Arquitectura en 4 capas con Oracle 12c como persistencia.
""",
}

OUT:error_example{
  profile:"OUT-ERROR",
  example:"""
OUT-ERROR
  handler:    blueprint.ready
  code:       MATURATION_INCOMPLETE
  gates:
    ❌ has_work_procedure
    ❌ has_required_validations
  hint:       Completa los 2 gates pendientes antes de llamar ready().
  — 4/6 gates aprobados. Faltan: procedure, validations.
""",
}


$4.3: PROFILE RULES

AXM:profile_rules{
  prefer_min:"OUT-MIN is the DEFAULT. Use it unless the interaction type clearly requires another profile.",
  hcortex_always:"ALL profiles use HCORTEX formatting: vertical layout, no comma-separated key=value lines, no abbreviations.",
  summary_always:"Every CORTEX-OUT block ends with ' — ' followed by a one-line natural language summary.",
  error_always_actionable:"OUT-ERROR must include a hint. Never just 'ERROR' — say what to do next.",
  tables_over_prose:"When comparing 3+ items, use a markdown table. When listing 3+ items, use bullets. Never use prose paragraphs for structured data.",
  diagrams_over_prose:"When explaining architecture, flow, or relationships, prefer PUML diagram in a code block over prose description.",
  upgrade_dont_downgrade:"If in doubt between MIN and AUDIT, use MIN. If in doubt between AUDIT and FULL, use AUDIT. Err on the side of less output.",
}


$5: BRAIN SYNC — AUTO-UPDATE BRAIN.CORTEX (sync_brain)

IDN:brain_sync{ name:"sync_brain", location:"src/arqux/sync.py", purpose:"Automatically update brain.cortex (WRK:current, FCS:current, metrics) after every successful handler mutation. Eliminates cognitive dissonance between execution and brain state." }

AXM:fail_silent{ sync_brain() never interrupts the calling handler. Errors are logged and swallowed. The handler always completes normally. }

HDL:sync_brain{ signature:"sync_brain(project_root, event, focus?, metrics?, detail?)", purpose:"Update WRK:current, update FCS:current (if focus=), log metrics. Called as last line before return in mutating handlers.", event:"Canonical event name: 'blueprint.approve', 'task.complete', 'cycle.create'", focus:"New FCS value. Only for major events (approve, create, close).", metrics:"Dict of counters: {'blueprints_done': 17}", detail:"Human-readable detail about the event" }

STP:integrated_handlers{ count:15, modules:["blueprint (create, complete, approve, cancel, ready)", "task (create, complete)", "cycle (create, close)", "skill (edit)", "project (bind)", "cortex (record_lesson_handler)"], note:"Each handler calls sync_brain() as its last non-return line." }

AXM:handler_responsibility{ Each mutating handler is responsible for calling sync_brain() explicitly. No middleware. The handler calls it as the last line before returning success. }

AXM:no_read_sync{ Read-only handlers (list, read, get, status, lessons) MUST NOT call sync_brain(). The test_sync_brain.py test verifies this with a grep check. }

AXM:identity_skip{ identity.record already has built-in brain sync via its auto-trigger mechanism (syncs LNG to brain + scans for patterns). Adding sync_brain there would be redundant — the auto-trigger IS the sync. }


$6: KEY PRINCIPLES

AXM:density_over_prose{ Every token consumed by prose is a token NOT used for thinking. CORTEX delivers 8x the information per token. Write for the LLM reader, not the human reader. }

AXM:memory_evolves{ Agent memory is a living document. LNG entries accumulate. cortex.learn scans for patterns and proposes elevations to KNW. }

AXM:one_format_everywhere{ Governance state, agent docs, skills, output, and agent memory — ALL use the same sigil format. }


$7: PLANTUML IN HCORTEX DOCUMENTS

AXM:puml_mandatory{ Every Blueprint (BLP-NNN.md) MUST include three PUML diagrams: Context (§5), Technical Design (§8), and Operational Design (§9). These diagrams are the PRIMARY mechanism for communicating intent between Architect and Executor. }

STP:puml_diagrams{
  context:{
    name:"Context Diagram — UML deployment/context",
    purpose:"Shows the environment: actors, systems, databases, external services.",
    rule:"Every external dependency must be drawn. Nothing is 'obvious'.",
    min_elements:"3+ actors/systems with labeled relationships.",
  },
  technical:{
    name:"Technical Design — UML component diagram",
    purpose:"Shows components to build, their responsibilities, and interfaces.",
    rule:"Each component has ONE responsibility. Each arrow has ONE purpose.",
    min_elements:"3+ components, interfaces, data flow arrows.",
  },
  operational:{
    name:"Operational Design — UML sequence diagram",
    purpose:"Step-by-step execution plan with phases, actions, and expected outputs.",
    rule:"The agent follows this like a script. Ambiguous step = incomplete diagram.",
    min_elements:"3 phases with clear inputs, actions, and expected responses.",
  },
}

AXM:diagrams_are_contracts{ The three diagrams ARE the design contract between Architect and Executor. If the executor builds something different from what the diagrams show, it's a deviation. The diagrams are interpretable by both humans (visual) and agents (UML notation is machine-parseable). }


$8: IDENTITY SERVICE (P2 IdentityManager)

IDN:identity_service{
  name:"IdentityManager",
  module:"src/arqux/identity.py",
  purpose:"Central resolver for agent identities. Replaces identity_resolver.py (BLP-008 GOV-001 P2.2).",
  relationship:"Used by permisos.py PermissionContext.from_env() to resolve agent_id -> canonical name",
}

AXM:identity_manager_only{ All identity resolution MUST go through IdentityManager. Direct file access to identities/ is DEPRECATED. identity_resolver.py is replaced. }

HDL:identity_manager_resolve{
  signature:"IdentityManager(project_root=...).resolve(name) -> CortexArtifact",
  purpose:"Resolve an agent name to its CortexArtifact identity file.",
  raises:"IdentityNotFoundError if <name>.cortex not found",
}

HDL:identity_manager_bind{
  signature:"IdentityManager(project_root=...).bind_to_session(name) -> SessionContext",
  purpose:"Resolve + extract AXM/LIM contracts into SessionContext for command execution.",
}

HDL:identity_manager_elevate{
  signature:"elevate_to_identity(agent, lesson_id, contract_type, *, pattern, evidence_ref) -> dict",
  purpose:"Inject AXM or LIM sigil into an identity file (Governor-only flow).",
  note:"Only sanctioned way to mutate identity files. Called by Governor after learning elevation approval.",
}

HDL:identity_manager_list{
  signature:"list_identities() -> list[str]",
  purpose:"Return sorted list of identity names from .arqux/identities/",
}

STP:identity_path_resolution{
  project_level:"IdentityManager(project_root=/path/to/ARQUX) -> /path/to/ARQUX/.arqux/identities/",
  workspace_level:"If no project_root, uses packaged identities or ~/.arqux/identities/",
  note:"Uses find_project_root() internally for consistent path resolution (BLP-008 GOV-001 P2.3).",
}