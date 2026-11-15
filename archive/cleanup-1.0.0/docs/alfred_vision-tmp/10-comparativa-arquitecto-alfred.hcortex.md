# 10-comparativa-arquitecto-alfred.hcortex.md
> Análisis comparativo-asociativo: Visión del Arquitecto (arch_vision) vs Visión de Alfred (alfred_vision)
> Proyecto: ARQUX
> Generado: 2026-07-12
> Idioma: español
> Autor: Alfred

---

$0: METADATA
IDN:comparativa{ name:"Comparativa Arquitecto-Alfred", version:"1", purpose:"Comparar la vision del Arquitecto (12 workflows, handlers, catalogo) con la vision de Alfred (3 categorias, 4 movimientos, handlers nativos) para validar consistencia y trazar correspondencias.", arch_vision:13, alfred_vision:3, asociaciones:15 }
WRK:comparativa{ status:"analisis", basa_en:"arch_vision/ (13 docs) + alfred_vision/ (3 docs)" }

---

$1: MAPA GENERAL

```
ARQUITECTO (arch_vision/)                ALFRED (alfred_vision/)
══════════════════════════════           ══════════════════════════════

13 documentos                           →  3 documentos (+4 planeados)
  handlers-catalogo.hcortex.md          →  00-MANIFIESTO.hcortex.md
  w00-w11 (12 workflows)                →  01-workflows-alfred.hcortex.md
                                         02-arquitectura-nativa.hcortex.md

3.809 líneas totales                    →  852 líneas totales
```

**No son visiones en competencia.** Son dos niveles de abstracción:
- El Arquitecto define el **qué** (componentes, estructura, handlers)
- Alfred define el **cómo** (interacción, flujo, experiencia del agente)

Una no reemplaza a la otra. Se complementan.

$2: TABLA COMPARATIVA — 16 EJES

| Eje | Arquitecto (arch_vision) | Alfred (alfred_vision) | Asociacion |
|---|---|---|---|
| **Entry point** | w00 triage: 5 ramas (BLP, tarea, ciclo, proyecto, consulta) | Una pregunta: "¿Acción acotada con intención clara?" → Tarea o BLP | Alfred simplifica el arbol. El Arquitecto define los casos; Alfred los agrupa. |
| **Estructura de trabajo** | 12 workflows (w00-w11) | 3 categorías (CX, CC, OP) + mecanismos flexibles | Los 12 workflows existen, pero Alfred los agrupa por tipo de interacción. No se pierde ninguno. |
| **Movimientos por tarea** | 3: Marco → Ejecutar → Cierre | 4: Marco → Revisar → Ejecutar → Cierre | Alfred añade el paso de **aprobación explícita** que en arch_vision estaba implícito. |
| **Evidencia** | pulse.jsonl separado + brain.cortex | PULSE en brain.cortex §7 | Alfred unifica. Un solo archivo, una sola fuente de verdad. |
| **Acceso a datos** | Agente lee filesystem (directorios, archivos sueltos) | Handlers nativos exponen todo | Alfred abstrae. El agente no sabe si el backend es archivos, DB o API. |
| **Formato de handlers** | Parámetros estructurados (obj, ac, priority...) | Canal I: contenido CORTEX como entrada | Ambos coexisten. El canal I es un wrapper sobre los parámetros estructurados. |
| **Triage** | Árbol técnico (BLP vs tarea vs ciclo vs proyecto vs consulta) | Pregunta natural: "¿acción acotada?" | Alfred traduce la clasificación técnica a lenguaje natural. El Arquitecto define la semántica. |
| **Aprobacion** | task.create → ejecutar | task.create → presentar → "¿Apruebas?" → ejecutar | Alfred explicita la compuerta de gobierno que en arch_vision se daba por sentada. |
| **BLP** | w08: 4 handlers, 3 interacciones, blueprint.synthesize | Conversación de diseño → synthesize → presentar → "¿Apruebas?" | Mismo flujo. Alfred añade la revisión explícita antes de crear tareas derivadas. |
| **Tarea** | w04: task.create → claim → evidence → complete | task.create → presentar → ejecutar → complete | Alfred fusiona claim + evidence intermedia en "ejecutar". El gobierno se mantiene. |
| **Contexto** | w01 (workspace) + w02 (project) + w03 (session) = 3 workflows | CX: handlers nativos (context.detect, project.current, cycle.current) | Alfred unifica 3 workflows en 1 categoría. Los 3 siguen existiendo como mecanismos internos. |
| **Conducta** | w05 (identity) + w06 (adoption) + w10 (handoff) = 3 workflows | CC: identity.record + adoption + handoff como handlers directos | Alfred reduce 3 workflows a handlers. La conducta no necesita proceso — es acción directa. |
| **Operacion** | w04 + w07 + w08 + w09 + w11 = 5 workflows | OP: task (4 mov) + BLP (diseño) + skills + crud + repair | Misma cobertura. Alfred unifica bajo 1 categoría con mecanismos específicos. |
| **Modelos debiles** | No especificado. Se asume el mismo diseño para todos. | NANO (solo task+identity), LITE (CX+CC+OP parcial), FULL (completo) | Alfred introduce tiers. El Arquitecto define el sistema máximo; Alfred lo escala hacia abajo. |
| **Skills** | w07: skill lifecycle como workflow separado | Skill como herramienta bajo demanda (no workflow) | Alfred baja w07 de workflow a skill. Se carga solo cuando se necesita. |
| **Reparacion** | w11: cortex file repair como workflow separado | Repair como handler directo (cortex.verify + repair) | Alfred baja w11 de workflow a handler. Si un archivo está roto, se repara, no se "workflowea". |

$3: MAPA DE CORRESPONDENCIA — 12 WORKFLOWS → 3 CATEGORIAS

```
ARCH_VISION                    ALFRED_VISION
──────────                     ─────────────

w00 triage           ─────     Triage: "¿Acción acotada?" + aprobación

w01 workspace-init   ─┐
w02 govern-project   ─┤──     CX (Contextual): handlers nativos
w03 session-start    ─┘

w04 reactive-task    ─┐
w08 blueprint        ─┤──     OP Tarea: 4 movimientos (Marco→Revisar→Ejec→Cerrar)
                      │       OP BLP: diseño conversacional + approve

w07 skill-lifecycle  ─┤──     Herramienta bajo demanda (skill)
w09 crud-blocked     ─┤──     Handlers directos (cortex.entry.add, etc.)
w11 cortex-repair    ─┘       Handlers directos (cortex.verify, repair)

w05 identity-evol.   ─┐
w06 agent-adoption   ─┤──     CC (Conductual): handlers directos + lecciones
w10 identity-handoff ─┘
```

**Ningún workflow del Arquitecto se pierde.** Todos se mapean a un
mecanismo en la visión de Alfred. Algunos se fusionan (w01/w02/w03),
otros se simplifican de workflow a handler directo (w05/w06/w07/w09/w10/w11).

$4: DONDE ALFRED AÑADE GOBIERNO QUE ARCH_VISION NO ESPECIFICA

| Aspecto | arch_vision | alfred_vision |
|---|---|---|
| **Aprobacion previa** | No explicita. task.create → claim → evidencia → complete | **Obligatoria.** task.create + "¿Apruebas?" + PULSE review approved |
| **PULSE en brain.cortex** | pulse.jsonl separado + brain.cortex separado | **Unificado.** brain.cortex §7 contiene el pulso |
| **Sin filesystem** | Agente lee .arqux/ directamente | **Handlers nativos.** El agente no sabe qué es un directorio |
| **Canal I** | No existe en la definición de handlers (parámetros planos) | **Content CORTEX.** El handler acepta CORTEX como entrada |

**Nota importante:** El Arquitecto definió el "qué" (handlers, workflows).
El "cómo" (aprobación, unificación, canal I) lo añade Alfred desde la
perspectiva de quien ejecuta. No contradicen — **completan**.

$5: DONDE ALFRED SIMPLIFICA SIN PERDER GOBIERNO

| Simplificación | arch_vision | alfred_vision | ¿Se pierde gobierno? |
|---|---|---|---|
| w01/w02/w03 → CX | 3 workflows separados | 1 categoría + handlers | No. Los handlers existen. El agente los invoca igual. |
| w05/w06/w10 → CC | 3 workflows separados | handlers directos | No. identity.record + adoption + handoff registran evidencia. |
| w07/w09/w11 → handlers | 3 workflows separados | handlers directos | No. Son operaciones atómicas. No necesitan coreografía. |
| pulse.jsonl + brain.cortex | 2 archivos | 1 archivo (brain.cortex) | No. PULSE en §7 preserva toda la trazabilidad. |
| task.claim mantenido | paso intermedio para multi-agente | se mantiene con claim para asignación divergente | Mínimo. El claim es necesario cuando el ejecutor difiere del creador. |

$6: DONDE ALFRED AÑADE COMPLEJIDAD (CON RAZON)

| Aspecto | arch_vision | alfred_vision | Por qué |
|---|---|---|---|
| Movimientos | 3 | 4 | La aprobación es el corazón del gobierno. No puede estar implícita. |
| Triage | Árbol de 5 ramas | Pregunta natural + categorización posterior | La pregunta natural es más robusta con modelos débiles. |
| Handlers | Firma fija | Canal I + firma fija coexisten | Canal I requiere parseo CORTEX. Es más trabajo de implementación. |
| Tiers | No existen | NANO/LITE/FULL | Los tiers son necesarios para modelos con distinta capacidad. |

$7: ASOCIACIONES CLAVE — LO QUE UNO APORTA AL OTRO

| Aporte del Arquitecto a Alfred | Aporte de Alfred al Arquitecto |
|---|---|
| La estructura de 12 workflows es la fuente de verdad | Los 4 movimientos (con aprobación) completan el ciclo de gobierno |
| Los 73 handlers son el vocabulario del sistema | Las 3 categorías (CX/CC/OP) organizan el vocabulario para el agente |
| pulse.jsonl como append log | PULSE en brain.cortex unifica y simplifica |
| La taxonomía de handlers por módulo | El canal I unifica la interfaz de todos los handlers |
| Los diagramas de secuencia por workflow | Los tiers (NANO/LITE/FULL) escalan el diseño a modelos débiles |
| La diferenciación tarea vs BLP | La pregunta "¿acción acotada?" hace la diferenciación navegable |

$8: CONSISTENCIA — VERIFICACION CRUZADA

| Afirmación de Alfred | Verificación en arch_vision |
|---|---|
| "Toda tarea usa task.create + task.complete" | Handler task.create y task.complete existen en REGISTRY |
| "BLP usa blueprint.synthesize" | Handler blueprint.synthesize está en el catalogo como nuevo |
| "PULSE es brain.cortex §7" | brain.cortex existe. §7 no estaba definido — Alfred lo añade |
| "Handlers nativos: context.detect, project.current, etc." | No existen hoy en REGISTRY. Son propuesta de Alfred |
| "4 movimientos: Marco, Revisar, Ejecutar, Cerrar" | No contradice a arch_vision. Añade explícito lo que estaba implícito |
| "w00 pregunta 'acción acotada?'" | Arch w00 muestra un árbol. Alfred lo simplifica a 1 pregunta |

**Puntos de fricción — RESUELTOS (2026-07-12):**
1. `context.detect` → **CREAR.** Handler nuevo para detectar .arqux/ sin filesystem.
2. `project.current` → **NO CREAR.** `cortex.read("brain.cortex")` es suficiente.
3. `identity.get("alfred")` — **CREAR.** Devuelve el cortex de la identidad solicitada.
   Si no existe, asume alfred por defecto y reporta que la identidad solicitada no existe.
   Más eficiente que listar identidades.
4. PULSE en brain.cortex → **SÍ, CON ÁMBITO POR DESTINATARIO.** El pulso lleva `from` y `to`.
   Cada agente lee los pulsos donde `to = self` o `from = self`.
   Los pulsos externos (`from=jarvis, to=alfred`) entran en la rotación de Alfred.
   Los pulsos propios con destinatario externo (`from=alfred, to=jarvis`) no entran en
   la rotación local — van al destinatario.
5. task.claim → **MANTENER.** Para asignación divergente (multi-agente). El claim es necesario
   cuando un agente diferente al que creó la tarea la ejecuta.

---

$11: REVISION

ERR:comparativa{ version:"2", generated:"2026-07-12", author:"Alfred", arch_docs:13, alfred_docs:3, ejes_comparados:16, workflows_mapeados:12, fricciones_resueltas:5, estado:"analisis + resoluciones del Arquitecto" }
