$0

# -- $0: CORTEX-INTERNAL SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Concept definition
# KNW   | knowledge  | attrs      | B | Semantic       | Knowledge item
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# STP   | step       | attrs      | M | Working        | Procedure
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Guiding principle
# FCS   | focus      | attrs      | H | Working        | Active focus
# OBJ   | objective  | attrs      | H | Working        | Active objective
# SES   | session    | attrs      | M | Episodic       | Session record


$1: POR QUE CORTEX PARA EL AGENTE

KNW:density{ topic:"Ultra-densidad de informacion", content:"Una entrada LNG en 30 tokens reemplaza 250 tokens de prosa. El agente puede almacenar 8x mas informacion en el mismo espacio de contexto.", benefit:"Memoria nativa mas densa → menos tokens → mas contexto util disponible." }

KNW:scanability{ topic:"Escaneo vertical por sigilos", content:"El agente escanea LNG:, KNW:, FCS: como indices naturales. No necesita leer todo el archivo — los sigilos son marcadores que el LLM entiende sin parser.", benefit:"Recuperacion acelerada: busca el sigilo, no el parrafo." }

KNW:self_indexing{ topic:"Auto-indexacion", content:"Cada $N: es un indice. Cada sigilo es una categoria. El glosario $0 es la tabla de contenidos. El archivo se indexa a si mismo.", benefit:"Sin necesidad de sistema de indices externo. El formato ES el indice." }

KNW:dual_read{ topic:"Lectura dual LLM/humano", content:"Un archivo CORTEX con extension .md es legible por cualquier LLM (entiende sigilos nativamente) y cualquier humano (ve texto estructurado).", benefit:"Mismo archivo, dos lectores, cero conversion." }


$2: MEMORIA NATIVA DEL AGENTE

AXM:memory_in_cortex{ La memoria nativa del agente (memory.md, notes.md, o el archivo que use) debe usar contenido CORTEX con glosario $0. El archivo conserva su nombre y extension original. Solo cambia el contenido. }

KNW:sections_for_memory{ recommendation:"Estructura recomendada para memoria de agente:",
  sections:
    "$0: Glosario local de sigilos usados",
    "$1: IDENTITY → quien soy, mi rol, mi maestro",
    "$2: FOCUS → en que estoy trabajando ahora",
    "$3: OBJECTIVES → objetivos activos con criterios de exito",
    "$4: KNOWLEDGE → conocimiento tecnico y del dominio",
    "$5: LESSONS → lecciones aprendidas (LNG)",
    "$6: SESSIONS → registro de sesiones recientes",
    "$7: CONTEXT → contexto de trabajo actual",
}

STP:build_memory{
  1:"Crear archivo memory.md con $0 glosario y las secciones que necesites",
  2:"Escribir FCS:current{what, priority, status} al iniciar cada sesion",
  3:"Acumular LNG:name{type, cause, lesson} cuando aprendas algo",
  4:"Almacenar KNW:topic{topic, content} para conocimiento permanente",
  5:"Registrar SES:agent{input, output, role, outcome} al finalizar sesion",
  benefit:"Tu memoria crece en densidad, no en volumen."
}


$3: PLANES Y NOTAS DE TRABAJO

AXM:notes_in_cortex{ Notas de trabajo, planes de implementacion, y documentos de analisis deben usar formato CORTEX. La prosa solo para comunicacion directa con el Arquitecto. }

STP:implementation_plan{
  format:"plan.md con contenido CORTEX",
  example:
    "$0 glosario",
    "$1: GOAL → OBJ:plan{goal, success}",
    "$2: STEPS → STP:1{action}, STP:2{action}",
    "$3: RISKS → RSK:name{description, mitigation}",
    "$4: EVIDENCE → AUD:note{evidence}",
  benefit:"El plan se ejecuta en el mismo formato en que se lee. Sin traduccion."
}

STP:research_note{
  format:"research.md con contenido CORTEX",
  example:
    "$1: QUESTION → OBJ:research{goal}",
    "$2: FINDINGS → KNW:topic{topic, content}",
    "$3: CONCLUSIONS → LNG:insight{type, lesson}",
  benefit:"La investigacion queda estructurada y recuperable."
}


$4: SESIONES DE TRABAJO

STP:session_start{
  1:"Leer memory.md → cargar FCS y LNG como prioridad",
  2:"Cargar brain.cortex del proyecto activo → entender FCS, OBJ, KNW, RSK",
  3:"Registrar SES:alfred{input, role, outcome} al inicio",
  format:"SES:alfred{input:\"objectivo de la sesion\", role:\"governor\", outcome:\"active\", date:\"hoy\"}"
}

STP:session_end{
  1:"Escribir LNG por cada leccion significativa de la sesion",
  2:"Actualizar FCS si el foco cambio",
  3:"Cerrar SES con outcome y output",
  4:"La memoria queda lista para la proxima sesion",
  format:"SES:alfred{input:\"...\", output:\"...\", role:\"governor\", outcome:\"ok\", date:\"hoy\"}"
}


$5: EJEMPLO COMPLETO DE MEMORY.MD

DESC:example_memory{
  A continuacion un ejemplo de como se veria memory.md de Alfred
  tras varias sesiones de trabajo con Arqux:
}

KNW:example_content{
  content:
    "$0",
    "",
    "# -- $0: ALFRED MEMORY GLOSSARY --",
    "# LNG | lesson | attrs | M | Episodic | Leccion aprendida",
    "# KNW | knowledge | attrs | B | Semantic | Conocimiento",
    "# FCS | focus | attrs | H | Working | Foco actual",
    "# SES | session | attrs | M | Episodic | Registro de sesion",
    "",
    "$1: IDENTITY",
    "IDN:alfred{role:\"governor\", master:\"el Arquitecto\"}",
    "",
    "$2: FOCUS",
    "FCS:current{what:\"Adopcion Arqux: inicializar ENVX_OPER\", priority:\"high\", status:\"current\"}",
    "",
    "$3: LESSONS",
    "LNG:path_param{type:\"process\", lesson:\"Siempre pasar path explicito a handlers. El cwd del MCP no es confiable.\"}",
    "LNG:identities_scope{type:\"rule\", lesson:\"Identidades solo a nivel workspace, no por proyecto.\"}",
    "LNG:cortex_write{type:\"process\", lesson:\"project.init(seed=) para brain. NO cortex.write para governance.\"}",
    "",
    "$4: SESSIONS",
    "SES:s01{input:\"Iniciar adopcion Arqux\", output:\"L-001 a L-005 registradas\", role:\"governor\", outcome:\"ok\"}",
    "SES:s02{input:\"Integrar CODEC-CORTEX\", output:\"write_cortex activado\", role:\"governor\", outcome:\"ok\"}",
}
