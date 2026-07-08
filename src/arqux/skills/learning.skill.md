$0

# -- $0: LEARNING SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Feature definition
# KNW   | knowledge  | attrs      | B | Semantic       | How it works
# STP   | step       | attrs      | M | Working        | Usage step
# FCS   | focus      | attrs      | H | Working        | When to use
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# SES   | session    | attrs      | B | Episodic       | Session record


$1: THE THREE LEVELS OF LEARNING

AXM:three_levels{ Todo aprendizaje en ArqUX se clasifica en UNO de tres niveles. El agente debe decidir el nivel al momento de registrar la lección — no después. La clasificación determina dónde persiste y quién puede accederla. }

KNW:level_conductual{ name:"CONDUCTUAL", dest:"identity.cortex $5 (LESSONS)", handler:"identity.record", scope:"Por agente", desc:"Afecta CÓMO se comporta este agente específico. Correcciones del Arquitecto sobre conducta, preferencias, estilo de comunicación, límites aprendidos, errores de protocolo repetidos. NO va aquí información del proyecto.", examples:["'No ejecutar sin autorización explícita del Arquitecto'", "'Esperar confirmación verbal antes de pasar un BLP a ready'", "'El Arquitecto prefiere HCORTEX en respuestas, no key=value'", "'Siempre pasar path explícito a handlers de descubrimiento'"] }

KNW:level_contextual{ name:"CONTEXTUAL", dest:"brain.cortex $5 (LESSONS) / $6 (KNOWLEDGE)", handler:"cortex.entry.add", scope:"Por proyecto", desc:"Afecta QUÉ se sabe de este proyecto. Decisiones técnicas, paradigmas aceptados, estándares del proyecto, blockers activos, recordatorios, esquemas DB, convenciones específicas. NO va aquí lo que aplica a todos los proyectos.", examples:["'En ENVX_INFRA se usa Docker Compose v2, no v1'", "'La BD FAMILIAR tiene ORA-04031 por CLEANUP_NON_EXIST_OBJ cada 12h'", "'El brain.cortex debe tener FCS con what no vacío y OBJ con goal'", "'Las skills se almacenan en .arqux/skills/ con formato CORTEX'"] }

KNW:level_procedimental{ name:"PROCEDIMENTAL", dest:"skills/ (.md)", handler:"skill.edit", scope:"Transversal (workspace)", desc:"Afecta CÓMO se hacen las cosas en TODOS los proyectos. Patrones de trabajo, flujos canónicos, conocimiento especializado reutilizable, estándares de formato, protocolos de gobierno. Lo que cualquier agente necesita saber para operar correctamente.", examples:["'BLP lifecycle: create → define → mature → ready → claim → execute → complete → approve'", "'Siempre ejecutar validate_file antes de embeber diagramas PUML en un BLP'", "'Los handlers se registran en __init__.py, no tienen lista paralela en la skill'", "'Session handlers: close al terminar, resume al empezar'"] }


$2: HOW TO CLASSIFY

FCS:decide{ when:"Cada vez que ocurre algo que el agente debe recordar", process:"Responder 3 preguntas:" }

STP:question_scope{ pregunta:"¿Aplica solo a mí como agente (conducta, preferencias, errores propios)?", si:"→ CONDUCTUAL → identity.record(lesson, kind='behavioral')", no:"→ Siguiente pregunta" }
STP:question_project{ pregunta:"¿Aplica solo a este proyecto específico (decisión técnica, blocker, estándar local)?", si:"→ CONTEXTUAL → cortex.entry.add(path, section='$5', sigil='LNG', name, value)", no:"→ Siguiente pregunta" }
STP:question_transversal{ pregunta:"¿Aplica a cualquier proyecto/agente (workflow, estándar, conocimiento especializado)?", si:"→ PROCEDIMENTAL → skill.edit(name, content)", no:"→ Revisar: toda lección debe caber en algún nivel" }


$3: HOW TO RECORD

HDL:identity.record{ signature:"record(lesson, kind?, cause?, agent_id?, path?)", purpose:"Registrar una lección CONDUCTUAL en identity.cortex ($5 LESSONS). kind: behavioral / process / format / rule / infrastructure. cause: qué provocó la lección.", example:"identity.record(lesson='Esperar confirmacion explicita antes de ready', kind='behavioral', cause='Arquitecto corrigio en BLP-002', path='./proyecto')" }

HDL:cortex.entry.add{ signature:"entry.add(path, section, sigil, name, value)", purpose:"Registrar una lección CONTEXTUAL en brain.cortex. section='$5' para LNG, section='$6' para KNW. value usa formato attrs CORTEX: 'key:val, key2:val2'", example:"cortex.entry.add(path='./proyecto/.arqux/brain.cortex', section='$5', sigil='LNG', name='ora_04031', value='type:infrastructure, cause:ORA-04031 cada 12h, lesson:CLEANUP_NON_EXIST_OBJ fragmenta shared pool')" }

HDL:skill.edit{ signature:"edit(name, content?, section?)", purpose:"Crear o actualizar una skill PROCEDIMENTAL. Sin content → lee la skill. Con content → escribe/reemplaza. Con section → reemplaza solo esa sección CORTEX.", example:"skill.edit(name='mi-skill', content='$0...')" }


$4: TIMING — CUÁNDO HACER QUÉ

AXM:record_inmediato{ La clasificación y registro ocurre INMEDIATAMENTE después de cada evento significativo: una corrección del Arquitecto, un error superado, un bug encontrado, un estándar descubierto. IDENTIFY FIRST. }

AXM:elevacion_diferida{ La elevación automática (cortex.learn) es un proceso POSTERIOR que detecta patrones: 3+ lecciones similares → propone consolidación. No reemplaza el registro inicial. }

FCS:when_to_record{ when:"Arquitecto corrige al agente" → action:"identity.record(kind='behavioral')" }
FCS:when_to_record{ when:"Se descubre un bug o workaround en un proyecto" → action:"cortex.entry.add(section='$5', sigil='LNG')" }
FCS:when_to_record{ when:"Se establece un estándar o patrón reusable" → action:"skill.edit(name, content)" }
FCS:when_to_record{ when:"Al cerrar un ciclo o completar un BLP" → action:"Revisar lecciones acumuladas y clasificar cada una" }
FCS:when_to_record{ when:"Arquitecto pregunta 'qué aprendiste'" → action:"Procesar AUDs pendientes, clasificar y registrar lo que falte" }


$5: THE ELEVATION ENGINE (CODEC-CORTEX CLE)

IDN:learning_engine{ name:"CODEC-CORTEX Learning Engine (CLE)", type:"adapter", location:"learning.py", handler:"cortex.learn", purpose:"Deterministic engine that scans brain.cortex, detects patterns in repeated lessons, and proposes elevations from LNG (lessons) to KNW (permanent knowledge) within the same level." }

KNW:how{ content:"The engine uses configurable Fibonacci policies in learn-policies.cortex. It scans LNG, SES, WRK, RSK entries and computes 4 scores: hotness (recurrence), promotion (elevation fitness), risk (cost of losing the entry), read_priority (P0-P5). When 3+ similar lessons appear, it detects a pattern and proposes elevation to KNW within the same destination." }

AXM:no_cross_level{ cortex.learn opera DENTRO de cada nivel. Una lección conductual (identity.cortex) se eleva a KNW conductual. Una lección contextual (brain.cortex) se eleva a KNW contextual. NO transpone entre niveles — esa decisión es del Arquitecto. }


$6: HANDLERS

HDL:cortex.learn{ signature:"learn(scope?, path?)", purpose:"Escanea brain.cortex (nivel contextual), ejecuta scoring completo (hotness, promotion, risk, priority), retorna candidatos a elevacion LNG→KNW." }

HDL:cortex.learn.elevate{ signature:"learn.elevate(candidate_id, apply?, confirm_hash?, path?)", purpose:"Eleva un candidato. Dry-run por defecto (solo muestra diff). apply=true escribe la elevación. Requiere confirm_hash exacto del dry-run para aplicar." }


$7: USAGE FLOW

STP:1{ action:"cortex.learn(path='./proyecto')", result:"N entradas escaneadas, M candidatos detectados", note:"Engine must be 'available'. Si 'unavailable', falta codec-cortex." }
STP:2{ action:"Revisar candidatos", result:"Cada uno muestra source, target, promotion_score, hotness_score" }
STP:3{ action:"cortex.learn.elevate(candidate_id='cand_001', path='./proyecto')", result:"Dry-run con diff del cambio propuesto" }
STP:4{ action:"cortex.learn.elevate(candidate_id='cand_001', apply=true, confirm_hash='abc...', path='./proyecto')", result:"Elevación escrita en brain.cortex" }
STP:5{ action:"cortex.read(path='./proyecto/.arqux/brain.cortex')", result:"KNOWLEDGE tiene nuevo contenido, LESSONS preserva LNG original" }


$8: POLICIES

KNW:policies{ content:"Policies en learn-policies.cortex. Primero busca `.arqux/learn-policies.cortex` en el proyecto; si falta, cae al template empaquetado en `src/arqux/templates/learn-policies.cortex`. Ajustar Fibonacci thresholds sin cambiar código." }

STP:customize{ 1:"Verificar si existe `.arqux/learn-policies.cortex` en el proyecto", 2:"Si no, copiar: `cp <package>/src/arqux/templates/learn-policies.cortex .arqux/`", 3:"Editar THR:golden_fibonacci{...} thresholds", 4:"cortex.learn usará los nuevos valores automáticamente" }
