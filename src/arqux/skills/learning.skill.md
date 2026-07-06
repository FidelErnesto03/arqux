$0

# -- $0: LEARNING SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Feature definition
# KNW   | knowledge  | attrs      | B | Semantic       | How it works
# STP   | step       | attrs      | M | Working        | Usage step
# FCS   | focus      | attrs      | H | Working        | When to use
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference


$1: QUE ES

IDN:learning_engine{ name:"CODEC-CORTEX Learning Engine (CLE)", type:"adapter", location:"learning.py", handler:"cortex.learn", purpose:"Motor deterministico de aprendizaje que escanea brain.cortex, detecta patrones en lecciones repetidas, y propone elevaciones de LNG (lecciones) a KNW (conocimiento permanente)." }

KNW:how{ content:"El motor usa politicas Fibonacci configurables en .arqux/learn-policies.cortex. Escanea entradas LNG, SES, WRK, RSK y calcula 4 scores: hotness (recurrencia), promotion (aptitud para elevacion), risk (costo de perder la entrada), read_priority (P0-P5). Cuando 3 o mas lecciones similares aparecen, detecta un patrón y propone elevarlas a KNW." }


$2: CUANDO USARLO

FCS:trigger{ when:"Despues de cerrar un ciclo", reason:"Es el momento natural: todas las tareas del ciclo completo, la evidencia acumulada" }
FCS:trigger{ when:"Cuando el Arquitecto pregunta 'que has aprendido'", reason:"El escaneo responde con datos concretos y candidatos" }
FCS:trigger{ when:"Antes de iniciar una fase nueva", reason:"Las lecciones de la fase anterior pasan a conocimiento permanente" }
FCS:trigger{ when:"Periodicamente, cuando hay muchas AUD sin procesar", reason:"El motor detecta patrones que el agente no vio manualmente" }


$3: HANDLERS

HDL:cortex.learn{ signature:"learn(scope?, path?)", purpose:"Escanea brain.cortex, ejecuta scoring completo, retorna candidatos a elevacion. scope=workspace incluye candidatos detallados." }

HDL:cortex.learn.elevate{ signature:"learn.elevate(candidate_id, apply?, path?)", purpose:"Eleva un candidato. Por defecto dry-run (solo muestra el diff). apply=true escribe la elevacion en brain.cortex." }


$4: FLUJO DE USO

STP:1{ action:"cortex.learn(path='./proyecto')", result:"Retorna N entradas escaneadas y M candidatos detectados", note:"Engine debe ser 'available'. Si es 'unavailable', codec-cortex no tiene el modulo learning." }
STP:2{ action:"Revisar los candidatos", result:"Cada candidato muestra source (fuente), target (destino), promotion_score y hotness_score", note:"Un LNG con hotness=5 y promotion=5 significa 3+ lecciones similares → patron" }
STP:3{ action:"cortex.learn.elevate(candidate_id='cand_001', path='./proyecto')", result:"Muestra el diff sin aplicar (dry-run)", note:"Siempre hacer dry-run primero para verificar que el cambio es correcto" }
STP:4{ action:"cortex.learn.elevate(candidate_id='cand_001', apply=true, path='./proyecto')", result:"Escribe la elevacion en brain.cortex: el LNG se conserva en LESSONS, el nuevo KNW aparece en KNOWLEDGE" }
STP:5{ action:"Verificar: task.read u otro handler confirma que el brain esta actualizado", result:"KNOWLEDGE section con el nuevo contenido" }


$5: POLITICAS

KNW:policies{ content:"Las politicas estan en .arqux/learn-policies.cortex. Se copian durante workspace.init y project.init. El Arquitecto puede editarlas directamente para ajustar umbrales Fibonacci (1,2,3,5,8,13,21), sigilos protegidos, o reglas de elevacion. No requieren cambios de codigo." }

STP:customize{ 1:"Editar .arqux/learn-policies.cortex", 2:"Ajustar THR:golden_fibonacci{...}", 3:"Por ejemplo: cambiar candidate:5 a candidate:3 para ser mas sensible", 4:"cortex.learn usara los nuevos umbrales automaticamente" }
