---
cycle_id: "CYCLE-05"
name: "CYCLE-05-recovery"
project_ref: "ARQUX"
status: "closed"
governor: "alfred"
created_at: "2026-07-14T13:30:00Z"
updated_at: "2026-07-14T18:30:00Z"
closed_at: "2026-07-15T18:02:52Z"
planned_start: "2026-07-14"
planned_end: ""
quality_gates@: "{"
has_clear_purpose: "true"
has_explicit_scope: "true"
has_measurable_objectives: "true"
has_operational_guidelines: "true"
has_control_points: "true"
aligns_with_project: "true"
_template_ref: "CYCLE_MANIFEST_TEMPLATE.md"
matured_at: "2026-07-14T16:42:12Z"
matured_by: "hermes"
---



# Manifiesto: CYCLE-05 — Recuperación Post-Auditoría

> Documento rector del ciclo. Basado en informe de auditoría CYCLE-04: `.arqux/audits/auditoria-ciclo-04.md`.  
> Fuente de verdad para todos los Blueprints de recuperación dentro de este ciclo.

---

## §1: Propósito

CYCLE-05 es un ciclo de **recuperación quirúrgica**. La auditoría de CYCLE-04 (17 BLPs, 9 líneas evolutivas) reveló:

- **1 regresión** por BLP-016: `compact_session_pulse` eliminada accidentalmente de pulse.py (18 tests rotos)
- **6 handlers faltantes:** handler.list no en REGISTRY, cortex.checkpoint, cycle.synthesize
- **1 violación activa:** skill.py:210 usa write_text contra AXM:codec_cortex_writer
- **5 handlers perdidos** entre auditoría jul-13 (91) y hoy (86)

**Objetivo:** Restaurar funcionalidad regresionada e implementar handlers críticos faltantes. No es un ciclo de nuevas features — es un ciclo de **reparación estructural**.

---

## §2: Alcance y Límites

**Dentro del alcance:**
- Restaurar `compact_session_pulse` en pulse.py + 18 tests
- Registrar `handler.list` en REGISTRY global
- Migrar `skill.py:210` de write_text → cortex_write
- Implementar `cortex.checkpoint` + WRK:current en brain.cortex §5
- Implementar `cycle.synthesize` + mature gateado + close verificado
- Configurar `ARQUX_AGENT_ROLE` en entorno
- Eliminar `mcp-handlers.skill.md` del filesystem
- Eliminar `brain.cortex.bak` (mover a backups/)
- Crear `protocol.onboard` como handler (o alias de `protocol.adopt`)

**Fuera del alcance:**
- Nuevas funcionalidades no relacionadas con hallazgos de auditoría
- Migración de datos legacy
- Refactors estructurales mayores
- Cambios en handlers no listados en prioridades

---

## §3: Objetivos

**CYC-OBJ-1 — CODEC-CORTEX como escritor exclusivo:**
- handler.list registrado en REGISTRY (descubrimiento runtime)
- 0 write_text en handlers para archivos .cortex
- mcp-handlers.skill.md eliminado del filesystem

**CYC-OBJ-2 — PULSE gestionado:**
- compact_session_pulse restaurada en pulse.py
- pulse.compact registrado en REGISTRY
- 18 tests verdes nuevamente

**CYC-OBJ-3 — Memoria y estado del agente:**
- cortex.checkpoint implementado
- WRK:current persiste entre turnos en brain.cortex §5
- session.bootstrap carga WRK:current

**CYC-OBJ-4 — Ciclo de vida del ciclo:**
- cycle.synthesize implementado
- cycle.mature gateado (rechaza si §9 compuertas false)
- cycle.close verificado (rechaza si BLPs no terminados)

**CYC-OBJ-5 — Protocolo de adopción:**
- protocol.onboard handler implementado (o adopt alias)
- ARQUX_AGENT_ROLE configurado
- brain.cortex.bak eliminado

---

## §4: Directrices

1. **Orden estricto:** Restaurar regresiones primero (pulse.compact), luego implementar faltantes
2. **Tests primero:** Cada fix incluye test de regresión antes de declarar completado
3. **Sin bypass:** Toda escritura de gobernanza usa MCP handlers (AXM:handlers_only)
4. **Un BLP por línea evolutiva:** Cada prioridad de la auditoría es un BLP independiente
5. **Evidencia por checkpoint:** blueprint.task() + sync_brain() tras cada tarea completada

---

## §5: Puntos de Control

| CP | Objetivo | Estado | Fecha |
|---|---|---|---|
| CP-01 | Restaurar pulse.compact + tests (BLP-001) | ☐ | — |
| CP-02 | handler.list en REGISTRY + skill.py:210 migrado (BLP-002, BLP-003) | ☐ | — |
| CP-03 | Fix blueprint path scoping bug (BLP-007) | ☐ | — |
| CP-04 | cortex.checkpoint + WRK:current (BLP-004) | ☐ | — |
| CP-05 | cycle.synthesize + mature + close (BLP-005) | ☐ | — |
| CP-06 | protocol.onboard + ARQUX_AGENT_ROLE + limpieza .bak (BLP-006) | ☐ | — |
| CP-07 | Revisión final — todas las compuertas ✅ | ☐ | — |

---

## §6: Blueprints (Índice)

| BLP ID | Título | Estado | Prioridad | Objetivo |
|---|---|---|---|---|
| BLP-001 | Restaurar pulse.compact — regresión BLP-016 | draft | critical | CYC-OBJ-2 |
| BLP-002 | handler.list en REGISTRY + eliminar mcp-handlers.skill.md | draft | critical | CYC-OBJ-1 |
| BLP-003 | Migrar skill.py:210 write_text → cortex_write | draft | high | CYC-OBJ-1 |
| BLP-004 | Implementar cortex.checkpoint + WRK:current | draft | high | CYC-OBJ-3 |
| BLP-005 | Implementar cycle.synthesize + mature gateado + close | draft | medium | CYC-OBJ-4 |
| BLP-006 | protocol.onboard + ARQUX_AGENT_ROLE + limpieza .bak | draft | medium | CYC-OBJ-5 |
| BLP-007 | Fix: blueprint handlers path scoping por ciclo activo | draft | critical | CYC-OBJ-1 |
| BLP-008 | Cierre CYCLE-05 — Observaciones Heimdall (OBS-01 a OBS-04) | draft | medium | CYC-OBJ-1 |

---

## §7: Estado y Métricas

**Estado actual:** draft  
**Total Blueprints:** 8 | **Draft:** 0 | **Madurando:** 0 | **Ready:** 0 | **En Progreso:** 0 | **Done:** 8  
**Progreso:** 100%  
**Próximo punto de control:** CP-01 — Restaurar pulse.compact  
**Iniciado:** 2026-07-14 | **Fin planificado:** —

---

## §8: Reglas del Ciclo

1. Orden de ejecución: CP-01 → CP-02 → CP-03 → CP-04 → CP-05 → CP-06 → CP-07
2. BLP-007 (fix de path scoping) se ejecuta en CP-03 para desbloquear handlers en BLPs subsiguientes
3. Cada BLP se completa antes de iniciar el siguiente (no paralelismo)
3. Verificar tests tras cada BLP: `pytest` sin regresiones
4. Si un fix rompe tests existentes, diagnosticar antes de continuar
5. Delegar ejecución a Jarvis, verificación a Heimdall cuando aplique

---

## §9: Contrato de Calidad

| Compuerta | Estado |
|---|---|
| has_clear_purpose | ✅ |
| has_explicit_scope | ✅ |
| has_measurable_objectives | ✅ |
| has_operational_guidelines | ✅ |
| has_control_points | ✅ |
| aligns_with_project | ✅ |

> Todas las compuertas en ✅. Ciclo listo para ejecución.
