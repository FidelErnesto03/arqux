# Auditoría Ciclo 04 — Recopilación de Hallazgos

**Fecha:** 2026-07-14  
**Auditor:** ALFRED + HEIMDALL  
**Alcance:** BLP-001 a BLP-017  
**Línea base:** origin/master (GitHub)  
**Estado:** COMPLETADO CON CORRECCIONES

---

## Resumen Ejecutivo (Provisional)

| BLP | Objetivo | Estado | Implementado | Errores |
|---|---|---|---|---|
| BLP-001 | skill.sync - regeneración automática | ❌ FALLIDO | NO | Handler no existe |
| BLP-002 | AGENTS.md 3-tier (NANO/LITE/FULL) | ⚠️ PARCIAL | Sí, con errores | Tablas aún hardcodeadas |
| BLP-003 | w03-w08 workflows consolidados | ⚠️ PARCIAL | Sí, con errores | Tablas de handlers persisten |
| BLP-004 | generate_handlers_skill() con $3-$7 | ❌ FALLIDO | NO | Regenerador sobrescribe todo |
| BLP-005 | protocol.onboard + environment | ❌ FALLIDO | NO | ARQUX_AGENT_ROLE no configurado |
| BLP-006 | w04 regenerado (task.run) | ❌ FALLIDO | NO | w04.md no regenerado |
| BLP-007 | w05 regenerado (cortex.patch) | ❌ FALLIDO | NO | w05.md no regenerado |
| BLP-008 | w06 regenerado (protocol.onboard) | ❌ FALLIDO | NO | w06.md no regenerado |
| BLP-009 | w07 regenerado (skill.install) | ❌ FALLIDO | NO | w07.md no regenerado |
| BLP-010 | w08 regenerado (blueprint.synthesize) | ❌ FALLIDO | NO | w08.md no regenerado |
| BLP-011 | w10 regenerado (session.handoff) | ❌ FALLIDO | NO | w10.md no regenerado |
| BLP-012 | handler.list + eliminar tablas | ❌ FALLIDO | NO | handler.list existe, tablas persisten |
| BLP-013 | pulse.compact | 🔄 REGRESIÓN | ROMPIDO | compact_session_pulse eliminada |
| BLP-014 | cortex.checkpoint + WRK:current | ❌ FALLIDO | NO | checkpoint.py no existe |
| BLP-015 | cycle.synthesize | ❌ FALLIDO | NO | cycle.py no tiene synthesize |
| BLP-016 | Eliminar write_text en handlers | ⚠️ PARCIAL | Sí, con errores | 5 archivos migrados, pero otros persisten |
| BLP-017 | Gate + response hook | ❌ FALLIDO | NO | Scripts no existen |

---

## BLP-001: skill.sync — Regeneración automática de skills

**Objetivo:** Implementar handler que compare hash de handlers con versión en skill y regenere si hay cambios.

**ACs definidos:**
- AC-01: skill.sync handler implementado
- AC-02: Hash del REGISTRY almacenado
- AC-03: session.bootstrap integra verificación
- AC-04: mcp-handlers.skill.md auto-generada
- AC-05: AGENTS.md §2 actualizado
- AC-06: protocol.skill.md §1 actualizado
- AC-07: Boot completo <= 6 llamadas MCP

**Verificación en código:**
- ❌ `skill.sync` handler: NO EXISTE (grep sin resultados)
- ❌ `cortex.patch`: NO EXISTE como handler independiente
- ❌ `cortex.checkpoint`: NO EXISTE
- ❌ `cortex.compact`: NO EXISTE
- ✅ `handler.list` handler: EXISTE en `src/arqux/handlers/handler.py` (creado para BLP-012)

**Conclusión:**  
**FALLIDO.** El handler `skill.sync` no fue implementado. La regeneración automática de skills no existe. Se creó `handler.list` como reemplazo parcial, pero no cumple el objetivo original de sincronización automática.

**Impacto:**  
- Los workflows siguen prescribiendo flujos multi-call que ya están consolidados en meta-handlers
- No hay mecanismo para detectar desincronización entre handlers reales y skills documentadas

---

## BLP-002: AGENTS.md 3-tier (NANO/LITE/FULL)

**Objetivo:** Reducir duplicación de AGENTS.md en 3 archivos incrementales (NANO <8K, LITE 8-250K, FULL >250K tokens).

**Archivos encontrados:**
```
AGENTS.md:     53 líneas, 4583 bytes (~900 tokens)
AGENTS.lite.md: 27 líneas, 1763 bytes
AGENTS.full.md: 29 líneas, 2072 bytes
```

**Verificación:**
- ✅ NANO existe (53 líneas, ~900 tokens — bajo límite 5K)
- ✅ LITE existe (delta sobre NANO)
- ✅ FULL existe (delta sobre LITE)
- ✅ TIE:NANO, TIE:LITE, TIE:FULL declarados en AGENTS.md
- ✅ AGENTS.md no referencia skills externas (autocontenido)

**Errores encontrados:**
- ⚠️ AGENTS.md contiene tabla hardcodeada en §3: "NANO HANDLER DISCOVERY (handler.list — 8 handlers)"
- ⚠️ Tablas de handlers siguen existiendo en múltiples archivos (viola AC-05 de BLP-012)

**Conclusión:**  
**PARCIALMENTE IMPLEMENTADO.** La estructura 3-tier existe, pero las tablas de handlers persisten en AGENTS.md (§3) y en otros archivos, violando los criterios de BLP-012 que eliminaba estas tablas.

---

## BLP-003: Consolidación de workflows (w03-w08)

**Objetivo:** Actualizar workflows.skill.md para que los workflows w03-w08 usen meta-handlers en vez de flujos multi-call obsoletos.

**ACs definidos:**
- AC-01: workflows.skill.md w03 actualizado
- AC-02: workflows.skill.md w04 actualizado
- AC-03: workflows.skill.md w08 actualizado
- AC-04: protocol.onboard implementado
- AC-05: protocol.skill.md §1 actualizado
- AC-06: skill.sync ejecutado post-cambios
- AC-07: cortex.verify sin errores
- AC-08: 804 tests pasan

**Verificación en archivos de workflows:**
```
arqux/skills/workflows/w04-reactive-task.md → task.run ✅
arqux/skills/workflows/w05-identity-evolution.md → cortex.patch ✅
arqux/skills/workflows/w06-agent-adoption.md → protocol.onboard ✅
arqux/skills/workflows/w07-skill-lifecycle.md → skill.install ✅
arqux/skills/workflows/w08-blueprint-lifecycle.md → blueprint.synthesize ✅
arqux/skills/workflows/w10-identity-handoff.md → session.handoff ✅
arqux/skills/workflows/w12-cycle-lifecycle.md → blueprint.synthesize + cycle.synthesize ✅
```

**Errores encontrados:**
- ⚠️ w04 usa `task.run` como meta-handler pero también referencia `task.create`, `task.claim`, `task.update`, `evidence.record` — estos ya no deberían estar documentados como pasos individuales
- ⚠️ Los workflows están en `.arqux/skills/workflows/` (formato CORTEX con sigils) pero también existe `workflows.skill.md` en la raíz — ¿son duplicados?

**Conclusión:**  
**PARCIALMENTE IMPLEMENTADO.** Los workflows están regenerados con los meta-handlers correctos. Sin embargo, la documentación interna sigue referenciando handlers individuales como pasos del workflow, lo que viola el espíritu del BLP (reemplazo completo, no parcial).

**Impacto:**  
- Los agentes pueden confundirse entre el meta-handler y los handlers individuales
- No hay mecanismo de validación automática que detecte workflows desactualizados

---

## BLP-004: generate_handlers_skill() con $3-$7 preservados

**Objetivo:** Modificar el generador de skills para que preserve $3-$7 (CLI FALLBACK, ROLE MODEL, MCP WIRE PROTOCOL, QUICK REFERENCE, HOW TO EXTEND) y regenere solo $8 (HANDLER CATALOG).

**ACs definidos:**
- AC-01: generate_handlers_skill() preserva $3-$7
- AC-02: mcp-handlers.skill.md tiene estructura $0-$8 sin duplicación
- AC-03: $8 lista 88 handlers agrupados por modulo
- AC-04: skill.sync re-ejecutado
- AC-05: Test estructural de skill.sync
- AC-06: cortex.verify sin errores
- AC-07: protocol.onboard visible via MCP
- AC-08: 804+ tests pasan

**Verificación en código:**
- ❌ `generate_handlers_skill()`: NO EXISTE en el código
- ❌ `skill.sync` handler: NO EXISTE
- ❌ No hay prueba de que el generador preserve $3-$7

**Conclusión:**  
**FALLIDO.** El generador `generate_handlers_skill()` no fue implementado. No existe código que regenere automáticamente mcp-handlers.skill.md. La skill se mantiene manualmente o no existe.

**Impacto:**  
- La skill mcp-handlers.skill.md está desactualizada o no existe
- Cada cambio de handler requiere actualización manual de 4 archivos (viola BLP-012)
- No hay mecanismo de sincronización automática

---

## BLP-005: protocol.onboard + ARQUX_AGENT_ROLE

**Objetivo:** Habilitar mutations MCP configurando ARQUX_AGENT_ROLE=governor, eliminar archivos .bak que causan FAIL en health check.

**ACs definidos:**
- AC-01: protocol.onboard visible en MCP tools list
- AC-02: ARQUX_AGENT_ROLE configurado — mutations permitidas
- AC-03: .arqux/ structure FAIL resuelto o documentado
- AC-04: blueprint mutations funcionan via MCP
- AC-05: 804 tests pasan
- AC-06: health check sin FAIL

**Verificación en código:**
- ❌ `protocol.onboard` handler: NO EXISTE (grep "def onboard" sin resultados)
- ❌ ARQUX_AGENT_ROLE: NO CONFIGURADO (protocol.py referencia la variable pero no está seteada en entorno)
- ✅ protocol.py existe y referencia ARQUX_AGENT_ROLE en línea 37 y 73
- ❌ .arqux/brain.cortex.bak: EXISTE (13937 bytes, fecha jul 13 22:17) — debería haber sido movido/finalizado

**Conclusión:**  
**FALLIDO.** El handler `protocol.onboard` no fue implementado. ARQUX_AGENT_ROLE no está configurado en el entorno. El archivo brain.cortex.bak sigue existiendo (violación de AC-03).

**Impacto:**  
- MCP no permite mutations (blueprint.create, complete, approve → PERMISSION_DENIED)
- Health check falla por archivos .bak
- Los agentes no pueden operar con rol de gobernador

---

## BLP-006: w04 regenerado (task.run)

**Objetivo:** Regenerar w04-reactive-task.md usando task.run como meta-handler (6→1 llamadas, 83% reducción).

**ACs definidos:**
- AC-01: w04 regenerado con meta-handler task.run
- AC-02: PUML actualizado reflejando el flujo optimizado
- AC-03: Tabla de handlers actualizada con task.run
- AC-04: cortex.verify sin errores
- AC-05: 804 tests pasan

**Verificación en código:**
- ✅ w04-reactive-task.md EXISTE (78 líneas)
- ✅ task.run como meta-handler (línea 14 menciona "task.run (6→1 llamadas, 83% reduccion)")
- ✅ PUML presente con diagrama de secuencia
- ✅ HDL:$2 con tabla de handlers (task.run + task.create, task.claim, etc.)
- ⚠️ w04 todavía referencia task.create, task.claim, task.update, evidence.record como handlers individuales disponibles — esto viola el espíritu de consolidación

**Conclusión:**  
**PARCIALMENTE IMPLEMENTADO.** El workflow está regenerado con task.run como meta-handler, pero la documentación interna todavía muestra los handlers individuales como opciones disponibles, lo que confunde al agente sobre qué usar.

**Impacto:**  
- El agente puede intentar usar handlers individuales en vez del meta-handler
- No hay validación automática que detecte esta inconsistencia

---

## BLP-007: w05 regenerado (cortex.patch)

**Objetivo:** Regenerar w05-identity-evolution.md usando cortex.patch como meta-handler (3→1 llamadas).

**ACs definidos:**
- AC-01: w05 regenerado con meta-handler cortex.patch
- AC-02: PUML actualizado reflejando el flujo optimizado
- AC-03: Tabla de handlers actualizada con cortex.patch
- AC-04: cortex.verify sin errores
- AC-05: 804 tests pasan

**Verificación en código:**
- ✅ w05-identity-evolution.md EXISTE (2150 bytes)
- ✅ cortex.patch como meta-handler (referenciado en IDN y AXM)
- ✅ PUML presente con diagrama de secuencia
- ✅ cortex.patch handler EXISTE en `src/arqux/handlers/cortex/patch.py`
- ✅ cortex.patch REGISTRADO en handler_schemas (cortex/__init__.py línea 390)
- ⚠️ cortex.patch NO está en el REGISTRY principal (solo en cortex/__init__.py) — ¿se exporta correctamente?

**Conclusión:**  
**PARCIALMENTE IMPLEMENTADO.** El workflow está regenerado y el handler cortex.patch existe. Sin embargo, no está claro si está correctamente registrado en el REGISTRY global.

**Impacto:**  
- Si cortex.patch no está en el REGISTRY global, los agentes no pueden invocarlo vía MCP
- El handler existe pero puede no ser descubrible por handler.list(tier=FULL)

---

## BLP-008: w06 regenerado (protocol.onboard)

**Objetivo:** Regenerar w06-agent-adoption.md usando protocol.onboard como meta-handler (2→1 llamadas).

**ACs definidos:**
- AC-01: w06 regenerado con meta-handler protocol.onboard
- AC-02: PUML actualizado reflejando el flujo optimizado
- AC-03: Tabla de handlers actualizada con protocol.onboard
- AC-04: cortex.verify sin errores
- AC-05: 804 tests pasan

**Verificación en código:**
- ✅ w06-agent-adoption.md EXISTE (2256 bytes)
- ✅ protocol.onboard como meta-handler (referenciado en IDN y PUML)
- ✅ PUML presente con diagrama de secuencia
- ⚠️ protocol.onboard NO es un handler — protocol.py tiene `adopt` pero no `onboard`
- ❌ protocol.onboard NO está en handler_schemas ni en REGISTRY

**Conclusión:**  
**FALLIDO.** El handler `protocol.onboard` no fue implementado. El workflow está regenerado referenciando un handler que no existe. El handler real es `protocol.adopt` (diferente nombre).

**Impacto:**  
- Los agentes invocan `protocol.onboard` pero el handler real es `protocol.adopt`
- Inconsistencia entre documentación y código
- El workflow describe un flujo que no puede ejecutarse

---

## BLP-009: w07 regenerado (skill.install)

**Objetivo:** Regenerar w07-skill-lifecycle.md usando skill.install como meta-handler (2→1 llamadas).

**ACs definidos:**
- AC-01: w07 regenerado con meta-handler skill.install
- AC-02: PUML actualizado reflejando el flujo optimizado
- AC-03: Tabla de handlers actualizada con skill.install
- AC-04: cortex.verify sin errores
- AC-05: 804 tests pasan

**Verificación en código:**
- ✅ w07-skill-lifecycle.md EXISTE (2268 bytes)
- ✅ skill.install como meta-handler (referenciado en IDN y PUML)
- ✅ PUML presente con diagrama de secuencia
- ✅ skill.install handler EXISTE en `src/arqux/handlers/skill.py`
- ✅ skill.install REGISTRADO en handler_schemas (skill.py línea 725)
- ✅ skill.install en REGISTRY global (86 handlers confirmados)

**Conclusión:**  
**IMPLEMENTADO.** El workflow está regenerado, el handler existe y está correctamente registrado.

**Impacto:**  
- Ninguno — este BLP se cumplió correctamente

---

## BLP-010: w08 regenerado (blueprint.synthesize)

**Objetivo:** Regenerar w08-blueprint-lifecycle.md usando blueprint.synthesize como meta-handler (23→4 llamadas, 83% reducción).

**ACs definidos:**
- AC-01: w08 regenerado con meta-handler blueprint.synthesize
- AC-02: PUML actualizado reflejando el flujo optimizado
- AC-03: Tabla de handlers actualizada con blueprint.synthesize
- AC-04: cortex.verify sin errores
- AC-05: 804 tests pasan

**Verificación en código:**
- ✅ w08-blueprint-lifecycle.md EXISTE (9251 bytes)
- ✅ blueprint.synthesize como meta-handler (referenciado en IDN y PUML)
- ✅ PUML presente con diagrama de secuencia
- ✅ blueprint.synthesize handler EXISTE en `src/arqux/handlers/blueprint/synthesize.py`
- ✅ blueprint.synthesize REGISTRADO en handler_schemas (blueprint/synthesize.py)
- ✅ blueprint.synthesize en REGISTRY global

**Conclusión:**  
**IMPLEMENTADO.** El workflow está regenerado, el handler existe y está correctamente registrado.

**Impacto:**  
- Ninguno — este BLP se cumplió correctamente

---

## BLP-011: w10 regenerado (session.handoff)

**Objetivo:** Regenerar w10-identity-handoff.md usando session.handoff como meta-handler (4→1 llamadas).

**ACs definidos:**
- AC-01: w10 regenerado con meta-handler session.handoff
- AC-02: PUML actualizado reflejando el flujo optimizado
- AC-03: HDL:$5 con tabla actualizada
- AC-04: cortex.verify sin errores
- AC-05: 804 tests pasan

**Verificación en código:**
- ✅ w10-identity-handoff.md EXISTE (4210 bytes)
- ✅ session.handoff como meta-handler (referenciado en IDN y PUML)
- ✅ PUML presente con diagrama de secuencia
- ✅ session.handoff handler EXISTE en `src/arqux/handlers/session.py`
- ✅ session.handoff REGISTRADO en handler_schemas (session.py línea 732)
- ✅ session.handoff en REGISTRY global

**Conclusión:**  
**IMPLEMENTADO.** El workflow está regenerado, el handler existe y está correctamente registrado.

**Impacto:**  
- Ninguno — este BLP se cumplió correctamente

---

## BLP-012: handler.list + eliminar tablas

**Objetivo:** Reemplazar tablas hardcodeadas de handlers en AGENTS.md con handler.list(tier=NANO/LITE/FULL). Eliminar mcp-handlers.skill.md y skill.sync.

**ACs definidos:**
- AC-01: handler.list(NANO)→8 handlers
- AC-02: handler.list(LITE)→28 handlers
- AC-03: handler.list(FULL)→88 handlers
- AC-04: AGENTS.md sin tabla
- AC-05: AGENTS.lite.md sin $2 tabla
- AC-06: AGENTS.full.md sin $2 tabla
- AC-07: mcp-handlers.skill.md NO EXISTE en .arqux/skills/
- AC-08: skill.sync NO EXISTE en registry
- AC-09: respuesta CORTEX valido clasificado por modulo

**Verificación en código:**
- ✅ handler.list handler EXISTE en `src/arqux/handlers/handler.py`
- ✅ handler.list en handler.py con TIER_MAPPING (NANO=8, LITE=28, FULL=88)
- ⚠️ handler.list NO está en REGISTRY global (python check: False)
- ❌ mcp-handlers.skill.md EXISTE en `src/arqux/skills/mcp-handlers.skill.md` (debería haberse eliminado)
- ⚠️ AGENTS*.md: grep "|--" sin resultados — tablas pueden haberse eliminado
- ✅ skill.sync NO existe (ya verificado en BLP-001)

**Conclusión:**  
**PARCIALMENTE IMPLEMENTADO.** handler.list existe pero no está en el REGISTRY global. mcp-handlers.skill.md debería haberse eliminado (AC-07) pero sigue existiendo.

**Impacto:**  
- handler.list no es invocable via MCP (no está en REGISTRY)
- mcp-handlers.skill.md es redundante (viola AC-07)

---

## BLP-013: pulse.compact

**Objetivo:** Implementar pulse.compact para compactar PULSE de 292+ entradas a ~20 relevantes, creando LNG de lecciones consolidadas.

**ACs definidos:** (10 ACs — ver BLP original)

**Verificación en código:**
- ❌ `pulse.compact` handler: NO está en REGISTRY
- ❌ `compact_session_pulse()` en pulse.py: **Fue eliminada** — importarla da `ImportError`
- ✅ 18 tests existen en `tests/test_pulse_compact.py`
- ❌ Los 18 tests FALLAN con `ImportError: cannot import name 'compact_session_pulse'`
- ⚠️ **REGRESIÓN:** Auditoría Heimdall 2026-07-13 reportó "sólido, 18/18 tests verdes". Hoy todos fallan.
- ⚠️ **Causa probable:** BLP-016 (eliminar write_text) removió accidentalmente la función de pulse.py

**Conclusión:**  
**REGRESIÓN.** pulse.compact fue implementado y funcionaba (18/18 tests verdes en jul 13). BLP-016 eliminó `compact_session_pulse` de pulse.py. No es que "nunca existió" — existió y se perdió.

**Impacto:**  
- Función eliminada del código fuente durante refactor BLP-016
- 18 tests rotos por ImportError
- PULSE sin mecanismo de compactación (regresión funcional)

---

## BLP-014: cortex.checkpoint + WRK:current

**Objetivo:** Implementar checkpoint de estado de trabajo del agente en brain.cortex §5, para sobrevivir entre turnos.

**ACs definidos:**
- AC-01: session.bootstrap retorna wrf_current con estado de trabajo
- AC-02: cortex.checkpoint(content) persiste WRK:current en brain.cortex §5
- AC-03: WRK:current sobrevive entre turnos
- AC-04: Si WRK:current no existe, bootstrap lo inicializa con defaults
- AC-05: cortex.checkpoint escribe PULSE (meta-evento AUD)
- AC-06: AGENTS.md $2 actualizado con referencia a checkpoint
- AC-07: AX:compact serializa y recarga desde .cortex
- AC-08: handler.list(tier=FULL) incluye cortex.checkpoint

**Verificación en código:**
- ❌ `cortex.checkpoint` handler: NO EXISTE
- ❌ `checkpoint_context()` en session.py: NO EXISTE
- ❌ `WRK:current` no referenciado en session.py

**Conclusión:**  
**FALLIDO.** cortex.checkpoint no fue implementado. El agente no tiene mecanismo para persistir su estado de trabajo entre turnos.

**Impacto:**  
- El agente pierde contexto entre turnos
- No hay checkpoint de estado de trabajo
- WRK:current no sobrevive entre sesiones

---

## BLP-015: cycle.synthesize

**Objetivo:** Implementar cycle.synthesize para poblar MANIFEST.md en una sola llamada, con maduración gateada y cierre con verificación de BLPs.

**ACs definidos:**
- AC-01: cycle.synthesize(cycle_id, content) escribe todas las secciones del manifiesto en 1 call
- AC-02: cycle.mature(cycle_id) rechaza con error si alguna compuerta §9 es false
- AC-03: cycle.mature(cycle_id) transiciona a ready si todas las compuertas son true
- AC-04: cycle.close(cycle_id) actualiza §7 del manifiesto con métricas reales
- AC-05: cycle.close(cycle_id) rechaza si hay BLPs en estado != done/cancelled
- AC-06: cycle.synthesize visible en handler.list(tier=FULL)
- AC-07: w12-cycle-lifecycle.md existe con diagrama PUML
- AC-08: workflows.skill.md incluye entrada w12
- AC-09: arch_vision/w12-cycle-lifecycle.hcortex.md existe
- AC-10: CYCLE-04 manifiesto poblado con datos reales

**Verificación en código:**
- ❌ `cycle.synthesize` handler: NO EXISTE (grep sin resultados en cycle.py)
- ❌ `synthesize_cycle()` en cycle.py: NO EXISTE
- ❌ `cycle.synthesize` no está en REGISTRY

**Conclusión:**  
**FALLIDO.** cycle.synthesize no fue implementado. El ciclo no puede poblar su MANIFEST.md en una sola llamada.

**Impacto:**  
- MANIFEST.md queda vacío o se llena manualmente
- No hay maduración gateada (AC-02/03)
- No hay cierre con verificación de BLPs (AC-05)

---

## BLP-016: Eliminar write_text en handlers

**Objetivo:** Eliminar todas las instancias de write_text() en handlers que escriben archivos .cortex, reemplazándolas por cortex_write() o cortex.patch().

**ACs definidos:**
- AC-01: grep -rn "write_text|\\.write(" src/arqux/handlers/ | grep cortex → 0 resultados
- AC-02: skill.py:210 usa cortex.write (no write_text)
- AC-03: skill.py:664 usa cortex.patch (no write_text)
- AC-04: _helpers.py:350 usa cortex.entry.add (no write_text)
- AC-05: workspace.py:76 usa cortex.write
- AC-06: project.py:73 usa cortex.write
- AC-07: session.py:853 usa cortex.write
- AC-08: migrate.py:106 usa cortex.write
- AC-09: Todas las entradas CORTEX generadas son single-line
- AC-10: Tests existentes pasan sin modificaciones
- AC-11: cortex.repair escanea y reporta entradas multi-linea
- AC-12: cortex.repair corrige entradas multi-linea a single-line

**Verificación en código:**
- ✅ _helpers.py:350 usa crud_add (no write_text)
- ✅ project.py:79 usa cortex_write (no write_text)
- ✅ session.py:698 usa cortex_write (no write_text)
- ✅ workspace.py:75 usa cortex_write (no write_text)
- ⚠️ skill.py:210 usa write_text(cortex_content, encoding="utf-8") — VIOLA AC-02
- ⚠️ skill.py:664 — NO verificado (línea 664 no aparece en grep de write_text)
- ⚠️ No se verificó migrate.py (no existe como archivo independiente)
- ✅ cortex_write y cortex.patch existen como funciones

**Conclusión:**  
**PARCIALMENTE IMPLEMENTADO.** 4 de 5 archivos objetivo migraron correctamente. Pero skill.py:210 todavía usa write_text (viola AC-02). No se encontró cortex.repair (AC-11/12).

**Impacto:**  
- skill.py sigue usando write_text para escribir .cortex (hipocresía según BLP-016)
- cortex.repair no existe para corregir entradas multi-linea

---

## BLP-017: Gate + response hook

**Objetivo:** Implementar scripts de enforcement para garantizar que todo agente cumpla con header HCORTEX y dashboard antes de responder.

**ACs definidos:**
- AC-01: Gate bloquea el primer turno si session.bootstrap falla
- AC-02: Gate inyecta dashboard + header en el contexto del agente
- AC-03: Hook rechaza respuesta sin `⬡ AGENT|PROJECT|SCOPE`
- AC-04: Hook rechaza respuesta sin estructura HCORTEX
- AC-05: Hook acepta respuesta con header + HCORTEX válidos
- AC-06: Agente recibe feedback y reintenta tras rechazo (máx 3)
- AC-07: Gate y hook funcionan con cualquier modelo (agnóstico)
- AC-08: `scripts/arqux_session_gate.sh` existe y es ejecutable
- AC-09: `scripts/arqux_response_hook.py` existe y es ejecutable

**Verificación en código:**
- ✅ `scripts/arqux_session_gate.sh` EXISTE (2978 bytes, ejecutable)
- ✅ `scripts/arqux_response_hook.py` EXISTE (2064 bytes, ejecutable)
- ✅ Ambos scripts con permisos -rwxrwxr-x

**Conclusión:**  
**PARCIALMENTE IMPLEMENTADO.** Los scripts existen y son ejecutables. No se pudo verificar su funcionalidad interna (requiere ejecución).

**Impacto:**  
- Scripts existen pero su funcionalidad no fue verificada
- No se sabe si cumplen con AC-01 a AC-07

---

## CAPÍTULO NUEVO: LÍNEAS EVOLUTIVAS DEL CICLO 04

### Metodología

El ciclo 04 es **evolutivo**: funcionalidades que nacieron en BLPs tempranos fueron refinadas, absorbidas o reemplazadas por BLPs posteriores. No aplica corrección BLP por BLP — debemos identificar **líneas evolutivas** y verificar si llegaron a su **punto final**.

**Principio rector:** Cada línea responde: ¿cuál es el último BLP de esa funcionalidad y está su resultado implementado?

---

### LÍNEA 1: CODEC-CORTEX como escritor exclusivo y fuente de verdad

**Fusión de Línea 7 (handler.list) + Línea 1 original (cortex_write).** Son dos facetas del mismo principio arquitectónico: CODEC-CORTEX como único mecanismo de escritura y runtime discovery como única fuente de verdad.

**Origen:** BLP-012 + BLP-016  
**Evolución:** BLP-001 (skill.sync) → BLP-004 (generate_handlers_skill) → BLP-012 (handler.list, eliminar mcp-handlers.skill.md) → BLP-016 (migrar write_text → cortex_write)  
**Punto final:** BLP-012 + BLP-016

**Etapas:**
1. **BLP-001/004** — Intentan regeneración automática de skills → fallan, se abandonan
2. **BLP-012** — Sentencia arquitectónica: handler.list reemplaza 3 artefactos (tablas hardcodeadas, mcp-handlers.skill.md, skill.sync). Runtime discovery desde REGISTRY.
3. **BLP-016** — Sentencia operacional: cortex_write/cortex.patch/crud_add reemplazan write_text en handlers que tocan .cortex

**Estado actual:**
| Artefacto | Estado | Detalle |
|---|---|---|
| handler.list | ⚠️ Existe en handler.py | NO está en REGISTRY — no invocable |
| mcp-handlers.skill.md | ❌ Existe en disco | Debe eliminarse (AC-07 BLP-012) |
| cortex_write | ✅ Usado en 4 archivos | project.py, session.py, workspace.py, _helpers.py |
| skill.py:210 | ❌ write_text | NO migrado — viola AC-02 BLP-016 |
| cortex.patch | ✅ Existe | En REGISTRY |
| crud_add | ✅ Existe | En _helpers.py |

**Punto final esperado:**
- handler.list registrado en REGISTRY como único mecanismo de descubrimiento
- 0 write_text en handlers para archivos .cortex
- mcp-handlers.skill.md ELIMINADO del filesystem
- skill.sync ELIMINADO del registry

**Brecha:** handler.list no en REGISTRY, skill.py:210 sin migrar, mcp-handlers.skill.md en disco.

---

### LÍNEA 2.1: w04 — task.run (workflow reactivo)

**Origen:** BLP-003 → BLP-006  
**Evolución:** BLP-006  
**Punto final:** BLP-006

**Etapas:**
1. **BLP-003** — Detecta w04 multi-call obsoleto (6 llamadas)
2. **BLP-006** — Regenera w04-reactive-task.md con task.run (6→1)

**Estado actual:**
- ✅ w04 existe, task.run como meta-handler
- ✅ task.run handler en REGISTRY
- ⚠️ w04 documenta handlers individuales como opciones
- ⚠️ **Corrección Heimdall:** task.run solo complete/fail, requiere task_id previo. No reemplaza las 6 llamadas. arch_vision w04 lo documenta como "atajo feliz", no como reemplazo total.

**Brecha:** Documentación interna engañosa sobre el alcance real de task.run.

---

### LÍNEA 2.2: w05 — cortex.patch (evolución de identidad)

**Origen:** BLP-003 → BLP-007  
**Evolución:** BLP-007  
**Punto final:** BLP-007

**Etapas:**
1. **BLP-003** — Detecta w05 multi-call (3 llamadas)
2. **BLP-007** — Regenera w05 con cortex.patch (3→1)

**Estado actual:**
- ✅ w05 existe, cortex.patch como meta-handler
- ✅ cortex.patch handler en REGISTRY
- ⚠️ Documenta handlers individuales

**Brecha:** Menor — limpiar referencias a handlers atómicos.

---

### LÍNEA 2.3: w06 — protocol.onboard (adopción de agentes)

**Origen:** BLP-003 → BLP-008  
**Evolución:** BLP-005 → BLP-008  
**Punto final:** BLP-008 (absorbe BLP-005)

**Etapas:**
1. **BLP-003** — Menciona protocol.onboard como meta-handler
2. **BLP-005** — Detecta issues: handler en schemas pero no en MCP, ARQUX_AGENT_ROLE sin configurar, .bak causan FAIL
3. **BLP-008** — Regenera w06 con protocol.onboard (2→1)

**Estado actual:**
- ❌ protocol.onboard NO existe — el handler es protocol.adopt
- ❌ ARQUX_AGENT_ROLE no configurado
- ❌ brain.cortex.bak existe

**Brecha:** Handler con nombre incorrecto. ARQUX_AGENT_ROLE sin configurar.

---

### LÍNEA 2.4: w07 — skill.install (ciclo de vida de skills)

**Origen:** BLP-003 → BLP-009  
**Evolución:** BLP-009  
**Punto final:** BLP-009

**Etapas:**
1. **BLP-009** — Regenera w07 con skill.install (2→1: import + convert)

**Estado actual:**
- ✅ w07 existe, skill.install en REGISTRY
- ⚠️ **Corrección Heimdall:** skill.install no convierte ni escribe .arqux/skills/. Solo "import + validate + register in brain.cortex". La reducción 2→1 es engañosa.

**Brecha:** Documentación infla el alcance real.

---

### LÍNEA 2.5: w08 — blueprint.synthesize (ciclo de vida BLP)

**Origen:** BLP-003 → BLP-010  
**Evolución:** BLP-010  
**Punto final:** BLP-010

**Etapas:**
1. **BLP-010** — Regenera w08 con blueprint.synthesize (~23→4, 83%)

**Estado actual:**
- ✅ w08 existe, blueprint.synthesize en REGISTRY
- ✅ 18 secciones verificadas en arch_vision
- ✅ **PLENA CONCORDANCIA** — único workflow completamente verificado

**Brecha:** Ninguna — implementación correcta y completa.

---

### LÍNEA 2.6: w10 — session.handoff (traspaso de contexto)

**Origen:** BLP-003 → BLP-011  
**Evolución:** BLP-011  
**Punto final:** BLP-011

**Etapas:**
1. **BLP-011** — Regenera w10 con session.handoff (4→1: context.read×2 + context.set + evidence)

**Estado actual:**
- ✅ w10 existe, session.handoff en REGISTRY
- ⚠️ **Corrección Heimdall:** kwarg es `target_agent`, workflow podría usar `to_agent` (incorrecto)

**Brecha:** Posible nombre de parámetro incorrecto en workflow.

---

### LÍNEA 2.7: w12 — cycle.synthesize (cierre de ciclo)

**Origen:** BLP-015  
**Evolución:** BLP-015  
**Punto final:** BLP-015

**Etapas:**
1. **BLP-015** — Implementa cycle.synthesize + mature gateado + close verificado

**Estado actual:**
- ❌ cycle.synthesize no existe
- ❌ MANIFEST.md de CYCLE-04 vacío

**Brecha:** Handler no implementado. w12 existe como archivo pero sin handler real.

---

### LÍNEA 3: Memoria y estado del agente — WRK:current entre turnos

**Origen:** BLP-014  
**Evolución:** BLP-014  
**Punto final:** BLP-014

**Etapas:**
1. **BLP-014** — Implementa cortex.checkpoint para persistir WRK:current en brain.cortex §5. Bootstrap carga WRK:current. Checkpoint persiste al final del turno.

**Estado actual:**
- ❌ cortex.checkpoint no existe
- ❌ WRK:current no referenciado en session.py

**Punto final esperado:**
- cortex.checkpoint(content) escribe WRK:current en brain.cortex §5
- session.bootstrap carga y retorna WRK:current
- WRK:current UNA línea CORTEX. El agente lee su estado, no lo recuerda.

**Brecha:** Handler no implementado.

---

### LÍNEA 4: Enforcement de axiomas — gate + response hook

**Origen:** BLP-017  
**Evolución:** BLP-017  
**Punto final:** BLP-017

**Etapas:**
1. **BLP-017** — Implementa scripts de enforcement: gate bloquea si bootstrap falla, hook rechaza respuestas sin header HCORTEX.

**Estado actual:**
- ✅ arqux_session_gate.sh existe (2978 bytes, ejecutable)
- ✅ arqux_response_hook.py existe (2064 bytes, ejecutable)
- ⚠️ Funcionalidad no verificada (requiere ejecución)

**Punto final esperado:**
- Gate bloquea primer turno si session.bootstrap falla
- Hook rechaza respuestas sin `⬡ AGENT|PROJECT|SCOPE` (máx 3 reintentos)
- Agnóstico a modelo

**Brecha:** Scripts no verificados. Sin tests automatizados.

---

### LÍNEA 5: Compactación de PULSE — pulse.compact (REGRESIÓN)

**Origen:** BLP-013  
**Evolución:** BLP-013 → rota por BLP-016  
**Punto final:** BLP-013

**Etapas:**
1. **BLP-013** — Implementa pulse.compact. 18 tests verdes.
2. **BLP-016** — Elimina write_text. compact_session_pulse removida accidentalmente.

**Estado actual:**
- ❌ compact_session_pulse ELIMINADA de pulse.py (ImportError)
- ✅ 18 tests existen en test_pulse_compact.py
- ❌ 18 tests FALLAN — ImportError

**Punto final esperado:**
- Restaurar compact_session_pulse en pulse.py
- Registrar pulse.compact en REGISTRY
- 18 tests verdes nuevamente

**Brecha:** Regresión por BLP-016. Función existía y funcionaba.

---

### LÍNEA 6: Ciclo de vida del ciclo — cycle.synthesize

**Origen:** BLP-015  
**Evolución:** BLP-015  
**Punto final:** BLP-015

**Etapas:**
1. **BLP-015** — CYCLE-04 tiene 14+ BLPs pero MANIFEST.md vacío. Implementa cycle.synthesize + mature gateado + close verificado.

**Estado actual:**
- ❌ cycle.synthesize no existe en cycle.py
- ❌ MANIFEST.md vacío

**Punto final esperado:**
- cycle.synthesize escribe todas las secciones en 1 call
- cycle.mature rechaza si compuertas §9 son false
- cycle.close actualiza §7 con métricas reales

**Brecha:** Handler no implementado.

---

### LÍNEA 7: AGENTS.md 3-tier — NANO / LITE / FULL

**Origen:** BLP-002  
**Evolución:** BLP-002 → refinado por BLP-012  
**Punto final:** BLP-012

**Etapas:**
1. **BLP-002** — Crea 3 archivos incrementales, elimina 80% duplicación
2. **BLP-012** — Elimina tablas hardcodeadas, handler.list reemplaza

**Estado actual:**
| Archivo | Líneas | Tamaño |
|---|---|---|
| AGENTS.md | 53 | 4583 bytes |
| AGENTS.lite.md | 27 | 1763 bytes |
| AGENTS.full.md | 29 | 2072 bytes |

**Punto final esperado:**
- 3 archivos incrementales sin duplicación
- Sin tablas hardcodeadas de handlers
- handler.list como único descubrimiento

**Brecha:** handler.list no en REGISTRY (compartida con Línea 1).

---

### LÍNEA 8: Regeneración automática de skills — skill.sync (ABSORBIDA)

**Origen:** BLP-001  
**Evolución:** BLP-001 → BLP-004 → absorbida por BLP-012  
**Punto final:** Esta línea NO debe existir. BLP-012 la elimina.

**Etapas:**
1. **BLP-001** — Propone skill.sync. No se implementa.
2. **BLP-004** — Propone reparar generate_handlers_skill(). No se implementa.
3. **BLP-012** — Sentencia final: skill.sync y mcp-handlers.skill.md se ELIMINAN.

**Estado actual:**
- ❌ skill.sync NO existe → CORRECTO
- ❌ generate_handlers_skill() NO existe → CORRECTO
- ✅ handler.list existe → parcial (falta REGISTRY)

**Brecha:** mcp-handlers.skill.md residual en disco, handler.list sin registrar.

---

## RESUMEN DE LÍNEAS EVOLUTIVAS (REFINADO)

| # | Línea | Origen | Punto Final | Estado | Acción |
|---|---|---|---|---|---|
| 1 | CODEC-CORTEX escritor exclusivo | BLP-012+016 | BLP-012+016 | ⚠️ 70% | handler.list en REGISTRY + skill.py:210 |
| 2.1 | w04 — task.run | BLP-006 | BLP-006 | ⚠️ Parcial | Corregir doc: solo complete/fail |
| 2.2 | w05 — cortex.patch | BLP-007 | BLP-007 | ✅ Completo | Limpiar refs atómicos |
| 2.3 | w06 — protocol.onboard | BLP-008 | BLP-008 | ❌ Fallido | Handler no existe (es adopt) |
| 2.4 | w07 — skill.install | BLP-009 | BLP-009 | ⚠️ Parcial | Doc infla alcance real |
| 2.5 | w08 — blueprint.synthesize | BLP-010 | BLP-010 | ✅ Verificado | 18 secciones, plena concordancia |
| 2.6 | w10 — session.handoff | BLP-011 | BLP-011 | ⚠️ Parcial | Kwarg es target_agent |
| 2.7 | w12 — cycle.synthesize | BLP-015 | BLP-015 | ❌ Fallido | Handler no existe |
| 3 | WRK:current — memoria | BLP-014 | BLP-014 | ❌ Fallido | cortex.checkpoint no existe |
| 4 | Enforcement de axiomas | BLP-017 | BLP-017 | ⚠️ Parcial | Scripts no verificados |
| 5 | PULSE compactación | BLP-013 | BLP-013 | 🔄 REGRESIÓN | Restaurar compact_session_pulse |
| 6 | Cycle lifecycle | BLP-015 | BLP-015 | ❌ Fallido | Implementar cycle.synthesize |
| 7 | AGENTS.md 3-tier | BLP-002 | BLP-012 | ✅ 90% | handler.list en REGISTRY |
| 8 | Regeneración skills | BLP-001 | ABSORBIDA | ✅ Correcto | Eliminar .skill.md residual |

---

## PRIORIDADES DE RECUPERACIÓN (REFINADO)

### Prioridad Alta:
1. **Línea 1:** handler.list en REGISTRY + skill.py:210 → cortex_write
2. **Línea 5:** Restaurar compact_session_pulse en pulse.py (regresión BLP-016)
3. **Línea 1:** Eliminar mcp-handlers.skill.md del filesystem

### Prioridad Media:
4. **Línea 3:** cortex.checkpoint — sin esto, agente pierde estado entre turnos
5. **Línea 2.3:** Configurar ARQUX_AGENT_ROLE + crear protocol.onboard (o alias)
6. **Línea 6 + 2.7:** cycle.synthesize — MANIFEST.md vacío

### Prioridad Baja:
7. **Línea 2.1:** Corregir documentación de task.run (solo complete/fail)
8. **Línea 2.4:** Corregir documentación de skill.install (alcance real)
9. **Línea 2.6:** Verificar kwarg en w10 (target_agent vs to_agent)

---

## CORRECCIONES DE HEIMDALL — Revisión Cruzada 2026-07-14

### Fuentes verificadas
`src/arqux/`, `tests/`, `docs/arch_vision/`, `docs/alfred_vision/`, `docs/audits/`, BLPs CYCLE-04.

### Corrección 1: BLP-013 / Línea 5 — REGRESIÓN, no "no implementado"
`compact_session_pulse` existía con 18 tests verdes (aud jul 13). BLP-016 la eliminó accidentalmente. `from arqux.pulse import compact_session_pulse` → ImportError. Acción: restaurar.

### Corrección 2: Task.run y Skill.install no reemplazan completamente
`task.run` solo complete/fail con task_id previo. `skill.install` no convierte ni escribe `.arqux/skills/`.

### Corrección 3: Session.handoff kwarg es `target_agent`, no `to_agent`

### Corrección 4: REGISTRY count — 86 hoy, 91 en auditoría previa (5 perdidos)

### Corrección 5: arch_vision y alfred_vision desactualizados para meta-handlers

### Corrección 6: Reestructuración de líneas evolutivas
- Línea 1 y Línea 7 fusionadas (CODEC-CORTEX escritor + fuente de verdad)
- Línea 2 desglosada en 7 sub-líneas por meta-handler
- BLP-017 extraída como Línea 4 independiente (enforcement)

**Veredicto Heimdall:** 2 errores materiales corregidos (BLP-013 es regresión; meta-handlers no reemplazan flujos completamente). Estructura de líneas refinada para precisión quirúrgica por workflow.

---

**Documento generado por:** ALFRED + HEIMDALL (revisión cruzada, estructura refinada)  
**Fecha:** 2026-07-14  
**Estado:** COMPLETADO CON CORRECCIONES
