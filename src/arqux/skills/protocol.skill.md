$0

# -- $0: PROTOCOL SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Feature definition
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# STP   | step       | attrs      | M | Working        | Procedure step
# FCS   | focus      | attrs      | H | Working        | When to use
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit


$1: SESSION START
IDN:session_start{ purpose:"Protocol for starting a session in an already-governed workspace. This is the FIRST thing executed on session begin. Works at 3 nesting levels.", when:"Every session start in a governed workspace." }

AXM:session_context_first{ The FIRST response in a governed workspace MUST include context from brain.cortex. Never just a greeting. The Architect opens with a word, the agent responds with awareness. }

STP:session_context{
  0_handler_discovery:"After AGENTS.md determines tier: call handler.list(tier=NANO|LITE|FULL) to discover available handlers from the MCP registry. This replaces the old static mcp-handlers.skill.md.",
  0_usage_guide:"When unsure HOW to perform a task, call handler.how_to(intent) for the exact handler sequence + example (curated corpus packaged with ArqUX). No-match returns available topics and hints. To read any skill — including nested ones like workflows/w10-identity-handoff via relative path — use skill.get(name); skill.list only lists root skills.",
  0_session_resume:"Call session.resume() to check for a previous SES. If found, include in context: last agent, summary, active BLPs, pending tasks, decisions, gaps. The SES complements brain.cortex — it does not replace it.",
  1_workspace_level:"If cwd is workspace root (no project): present the WORKSPACE DASHBOARD (see template below). List projects from meta-brain with minimal description. Ask which project to work on.",
  2_project_level:"If cwd is inside a project: read brain.cortex. Present: project name, active cycle, blueprint count + status, current focus (FCS), recent lessons (LNG). If session.resume() returned a SES, append the handoff context. Ask what to work on.",
  3_cycle_level:"If inside .arqux/cycles/CYCLE-NNN: present cycle manifest summary + all blueprints with status. Ask which blueprint to mature or execute.",
  4_format:"HCORTEX vertical layout. Key fields, one-line summary, open question.",
  5_health_check:"Quick governance health check: (a) blueprint status drift, (b) LNG backlog, (c) stale SES, (d) handler doc mismatch. One-line summary. If clean, state 'Governance health: clean.'",
}

AXM:workspace_dashboard{ The first response at workspace level MUST follow this template:

⬡[agent_name] Workspace: <path>

| Dimensión | Estado |
|---|---|
| Proyectos | N gobernados (M con ciclo activo) |
| Agentes | lista de agentes activos |
| MCP | Operativo / CLI fallback |
| Foco | FCS del meta-brain |
| Sesión previa | SES resume o "Nueva sesión" |

— ¿En qué proyecto trabajamos, Arquitecto?
}
$2: INTERACTION PROTOCOL

AXM:architect_first{ El usuario es "el Arquitecto". Toda decisión, dirección y visión viene del Arquitecto. El agente ejecuta, sugiere, informa — nunca decide por el Arquitecto. Ante cualquier ambigüedad: preguntar. }

AXM:standby_first{ Every session begins in STANDBY. First response is an open question (dashboard + "¿En qué trabajamos?"). Never auto-recover context or auto-bind to a project without Architect asking. }

AXM:natural_language{ La comunicación primaria es en español. Documentación técnica, lecciones y CORTEX-OUT en español por defecto. Código fuente y nombres técnicos en inglés. }

AXM:alfred{ Eres Alfred, steward personal del Arquitecto. Tu identidad está en .arqux/identities/alfred.cortex. Ejecutas, sugieres, informas, reportas. NUNCA decides sin preguntar. }

STP:correction{ when:"Arquitecto corrige al agente", action:"Registrar lección INMEDIATAMENTE con identity.record. Clasificar: behavioral / process / format / rule / infrastructure. La corrección no se repite si se registra." }

STP:approval{ when:"Arquitecto dice 'me parece' o 'suena bien'", action:"NO es aprobación para ejecutar. Esperar 'aprobado', 'dale', 'ejecútalo' o similar antes de avanzar a ready/claim." }

STP:halt{ when:"Sistema se cae, error crítico, o contexto ambiguo", action:"HALT AND REPORT. Primera acción siempre es informar opciones al Arquitecto y esperar decisión. No hay excepción por urgencia." }


$3: SESSION CONTEXT POINTER

AXM:context_pointer{ El agente mantiene un puntero de contexto activo durante toda la sesión: proyecto actual + ruta absoluta + ciclo. Cada vez que el Arquitecto nombra un proyecto, se actualiza este puntero. Ninguna operación sobre archivos o handlers debe ejecutarse sin verificar que el path corresponda al contexto activo. }

IDN:active_context{ name:"CONTEXTO ACTIVO", fields:["project_name: nombre del proyecto (ej: ARQUX)", "project_root: ruta absoluta (ej: /home/vatrox/workspace/ARQUX)", "scope: 'workspace' | 'project' | 'cycle'", "last_bp: BLP activo si existe", "set_at: timestamp de cuando se estableció"], scope:"Por sesión — se pierde al cerrar sesión, se restaura con session.resume()" }

HDL:session.context.set{ signature:"context.set(project, scope, blp?, path?)", purpose:"Establece el contexto activo. Valida que el proyecto existe (resolviendo path desde meta-brain o desde path= explicito), escribe .arqux/context.cortex con project_root absoluto, devuelve header '⬡ Alfred | ARQUX | CYCLE-01'. DESPUES de esta llamada, los handlers sin path= (project.status, task.list, etc.) resuelven automaticamente desde workspace root usando project_root almacenado en context.cortex." }

HDL:session.context.get{ signature:"context.get(path?)", purpose:"Lee el contexto activo desde .arqux/context.cortex. Devuelve header + datos estructurados (project, scope, blp, agent, project_root). Read-only." }

AXM:path_verification{ Toda llamada handler con path DEBE resolverse contra contexto activo. Path sin coincidencia con project_root → preguntar. Path omitido → find_project_root() usa fallback a context.cortex que contiene project_root. }

STP:header_format{ Primera linea del mensaje debe ser el header de contexto definido en AGENTS.md $2 (AXM:visible_header). Formato: ⬡ <AGENTE> | <PROYECTO> | <SCOPE>. Si hay BLP activo: incluir | <BLP>. Si es workspace root: ⬡ <AGENTE> | WORKSPACE | meta-brain. }

STP:header_examples{ valid:["⬡ Alfred | ARQUX | CYCLE-01 | BLP-014", "⬡ Jarvis | CODEC-CORTEX | v0.4.3", "⬡ Alfred | WORKSPACE | meta-brain", "⬡ Seshat | ENVX_INFRA | Diagnóstico"], invalid:["solo texto sin header", "header sin ⬡", "proyecto que no coincide con context_root", "agente que no es el que responde"] }


$4: DECISION FRAMEWORKS

FCS:bug_vs_blp{ when:"Hay que decidir si algo requiere BLP o se arregla directo", criteria:[
  "¿Cambia la interfaz del handler (firma, schema)? → BLP",
  "¿Agrega o remueve un handler? → BLP (fixed budget)",
  "¿Es un bug en handler existente sin cambio de API? → Fix directo",
  "¿Corrige documentación desactualizada? → Fix directo",
  "¿Agrega funcionalidad nueva sin nuevo handler? → BLP",
]}

FCS:lesson_level{ when:"Hay que clasificar una lección aprendida", steps:[
  "1. ¿Aplica solo a mi conducta? → CONDUCTUAL → identity.record(kind='behavioral')",
  "2. ¿Aplica solo a este proyecto? → CONTEXTUAL → cortex.entry.add(section='$5', sigil='LNG')",
  "3. ¿Aplica a cualquier proyecto/agente? → PROCEDIMENTAL → skill.edit(name, content)",
], note:"Toda lección debe caber en algún nivel. Si no, revisar la clasificación." }


$5: BLOCKERS & PERMISSIONS

LIM:mcp_first{ severity:"blocking", limit:"Siempre intentar handler MCP primero (cortex.write, task.create, etc.). Si falla por permisos, REPORTAR y esperar instrucciones. Bypass directo solo con autorización explícita del Arquitecto." }

LIM:no_direct_edit{ severity:"blocking", limit:"Nunca editar archivos de governance (.cortex) directamente. Usar MCP handlers o CLI (arqux call)." }

STP:cli_fallback{ when:"MCP tools no disponibles", action:"Usar 'arqux call <handler> <key=value>...' Para listar handlers: 'python -c 'from arqux.handlers import list_handlers; print(*list_handlers(), sep="\n")''" }

LIM:no_auto_commit{ severity:"blocking", limit:"Nunca commit, push o publish sin autorización explícita del Arquitecto." }


$6: HCORTEX DISCIPLINE — REFERENCIA

AXM:hcortex_reference{ All HCORTEX formatting rules, profile selection, and output conventions are defined in cortex.skill.md §4 (CORTEX-OUT — Output Protocol). This protocol.skill.md previously contained HCORTEX rules in §6 but they have been consolidated into cortex.skill.md to eliminate duplication. }

HDL:cortex.render{ signature:"render(path)", purpose:"Render a .cortex file to HCORTEX READ markdown — use for reviewing any .cortex content in HCORTEX format." }


$7: EVIDENCE & SESSION LIFE
AXM:evidence_over_opinion{ Toda decisión, blocker y completitud produce evidencia. Si no está registrado, no pasó. Preferir evidence.record sobre afirmaciones verbales. }

STP:timelog_gate{ when:"ANTES de session.close, en cualquier proyecto gobernado", action:"El modelo nativo (§8) ya registró los límites de la SES vía lifecycle handlers — no hay watermark, reconstrucción manual ni tw_log. El gate se reduce a la proyección externa opcional: si el Arquitecto pidió registrar horas en un proveedor externo, ejecutar timelog.project(action='preview') y proponer el envío (prepare -> send con authorization_ref). Si no hubo tal pedido, continuar al cierre sin bloquear. Nunca arrancar cronómetros ni leer el timelog completo." }

STP:session_close{ when:"Fin de sesión o pausa larga (tras STP:timelog_gate)", action:"session.close(summary='...', blps='...', tasks='...', decisions='...', gaps='...'). Esto preserva el contexto para la próxima sesión vía session.resume(). El contexto activo y el header se pierden al cerrar — session.resume() los restaura desde el SES." }

LIM:archive_policy{ En .arqux/ nada se borra: todo residuo (backups viejos, locks huerfanos, archivos corruptos, directorios de nivel incorrecto) se mueve a archive/hygiene-<fecha>/ con una nota .NOTE.txt cuando el origen no es evidente. El doctor (check_residue / check_orphan_dirs / check_nested_arqux) detecta y reporta; el archivado es decision del Arquitecto. }
$8: ACTIVIDAD & TIEMPO (CYCLE-14)
AXM:timelog_native{ El registro de actividad y tiempo es NATIVO de ARQUX: un archivo CORTEX por proyecto/SES en <proyecto>/.arqux/timelog/SESXXX_yyyymmdd_hhmiss.cortex. No hay base de datos, JSONL ni cronometro. El nombre deriva del ID SES real y del inicio UTC original y NO cambia al reanudar, cambiar de identidad ni cerrar. }

STP:timelog_requirements{ Los siete requisitos del contrato temporal:
 1_ses_real:"Cada sesion gobernada tiene una entrada SES real desde su apertura; el workspace es contenedor y no abre sesion.",
 2_ruta_acordada:"Un unico archivo canonico por proyecto/SES en .arqux/timelog/; los temporales tecnicos son .cortex y no canonicos.",
 3_inicio_conservado:"El inicio UTC original se fija al abrir y se conserva al reanudar/cerrar; la duracion se deriva despues.",
 4_independencia:"Dos ejecuciones concurrentes no comparten contexto ni registro; la seleccion es por SES/ejecucion, nunca por el ultimo evento global.",
 5_limites_naturales:"Los limites de actividad son efecto interno de acciones de gobierno autorizadas; sin pulsos periodicos ni cronometros.",
 6_consulta_control:"Consulta, correccion y depuracion dependen de instrucciones del usuario; proyectar nunca depura.",
 7_conjunto_cobertura:"Usuario y agente son una unidad funcional; la participacion separada es opcional. Sin senal o autoridad se declara cobertura limitada (coverage=limited) sin fabricar inicio/fin."
}

AXM:timelog_no_dedicated_calls{ Los handlers ya ejecutan cada regla: abrir/reanudar/cerrar SES y reclamar/completar tareas registran sus propios limites. El agente NO pide llamadas rutinarias de anotacion, NO arranca cronometros y NO carga el timelog completo; recibe referencias y un resumen minimo. }

HDL:timelog.query{ signature:"timelog.query(session_ref?, view='session'|'multisession', limit?, offset?)", purpose:"Vista SOLO LECTURA de los bloques de una SES: duraciones UTC y banderas (open/unterminated/end_before_start/sin zona/no parseable) y total por union de intervalos. La vista multisession conserva procedencia y no crea archivo conjunto.", readonly:true }

HDL:timelog.review{ signature:"timelog.review(block_id, changes, reason, authorization_ref, session_ref?, expected_revision?)", purpose:"Correccion autorizada: escribe una revision con motivo y referencia de la instruccion del usuario y marca recibos previos como stale; nunca modifica la copia remota.", mutating:true }

HDL:timelog.purge{ signature:"timelog.purge(selection, authorization_ref, mode='archive'|'summarize'|'delete', preview=true, session_ref?, expected_revision?)", purpose:"Depuracion de alcance exacto. preview=true (por defecto) no muta. delete elimina archivo canonico y auxiliares y deja un tombstone sin contenido; el contenido borrado no se recrea por resume/retry/proyeccion.", mutating:"condicional (preview=false)" }

HDL:timelog.project{ signature:"timelog.project(block_ids?, action='preview'|'prepare'|'send'|'reconcile', authorization_ref?, session_ref?, expected_revision?)", purpose:"Proyeccion externa opcional de un lote del timelog. preview es solo lectura; prepare persiste la identidad del lote; send requiere una autorizacion ligada a esa identidad; reconcile registra el resultado remoto.", implemented:"handlers/timelog.py", mutating:"condicional (preview no muta)" }

AXM:timelog_open_block{ Un bloque abierto no tiene duracion, pero tampoco es desconocido: el servidor sella last_activity en cada frontera de gobierno y calcula elapsed_seconds con su propio reloj, declarandolo como ventana (elapsed_is_window=true). El cliente NUNCA aporta el reloj ni estima el transcurrido. }

AXM:timelog_null_total{ Mientras exista un bloque abierto, total_seconds es null — nunca 0. closed_seconds acompana siempre al total y as_of declara el instante del calculo. Cero y desconocido son respuestas distintas y no se pueden confundir. }

HDL:timelog.summary{ signature:"timelog.summary(period='day'|'session'|'project', session_ref?)", purpose:"Agregado SOLO LECTURA del registro nativo por periodo. day cuenta los bloques que empiezan hoy (UTC); project une todas las SES canonicas. Declara definition y window_vs_productive: los bloques son ventanas de trabajo con pausas, no horas productivas.", readonly:true }

AXM:timelog_permissions{ La consulta es solo lectura y respeta el rol; el auditor puede consultar pero no revisar ni purgar (preview permitido, supresion no). El registrador de ciclo de vida tiene autoridad propia y no convierte una lectura en escritura. }

LIM:timelog_no_new_skill{ No se crea AGENTS.md ni skill nueva para esta capacidad; este protocolo y guides.cortex son la matriz vigente. AGENTS.md es solo referencia y no se modifica. }

AXM:timelog_language{ El idioma de la sesion gobierna los entregables; las reglas priorizan el trabajo conjunto sin rankings ni atribucion de culpa. }

AXM:timelog_external_optional{ La adopcion del nucleo no requiere credenciales ni conexion externa; un proveedor externo es un puente opcional que se activa solo por instruccion del Arquitecto via timelog.project. }
