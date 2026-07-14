---
cycle_id: "CYCLE-04"
name: "CORTEX-native-selfmanagement"
project_ref: ""
status: "ready"
governor: "alfred"
created_at: "2026-07-13T14:33:54Z"
updated_at: "2026-07-13T23:46:07Z"
closed_at: ""
planned_start: ""
planned_end: ""
quality_gates@: "{"
has_clear_purpose: "false,"
has_explicit_scope: "false,"
has_measurable_objectives: "false,"
has_operational_guidelines: "false,"
has_control_points: "false,"
aligns_with_project: "false,"
_template_ref: "CYCLE_MANIFEST_TEMPLATE.md"
matured_at: "2026-07-13T18:01:36Z"
matured_by: "hermes"
---



# Manifiesto: {name}

> Documento rector del ciclo. Define identidad, alcance, objetivos, directrices y puntos de control. Fuente de verdad para todos los Blueprints dentro de este ciclo.

---

## §1: Propósito

Implementar la vision CORTEX-native v0.5.0: eliminar duplicacion de handlers en AGENTS.md, implementar Dynamic Capability Discovery via handler.list, compactar PULSE via aprendizaje CORTEX, memoria de trabajo CORTEX-native con WRK:current, y ciclo de vida del ciclo como contenedor de gobierno.

## §2: Alcance y Límites

Dentro del alcance: handler.list, retiro de mcp-handlers.skill.md y skill.sync, pulse.compact, cortex.checkpoint, WRK:current, cycle.synthesize. Fuera del alcance: migracion de datos legacy, tests de integracion completos, cambios en handlers no relacionados.

## §3: Objetivos

CYC-OBJ-1: handler.list operativo — el agente descubre handlers dinamicamente desde el MCP registry. CYC-OBJ-2: PULSE gestionado — compactacion en cierre de sesion via aprendizaje CORTEX. CYC-OBJ-3: Memoria CORTEX-native — WRK:current checkpoint entre turnos. CYC-OBJ-4: Ciclos gobernados — cycle.synthesize + mature + close funcionales.

## §4: Directrices

1. Un BLP por funcionalidad — no se agrupan cambios no relacionados. 2. Cada BLP incluye diagrama PUML. 3. Tests antes de aprobar. 4. Sub-agentes para ejecucion (Jarvis executor, Heimdall auditor).

## §5: Puntos de Control

CP-01: handler.list + AGENTS alineados — 2026-07-13 completado. CP-02: PULSE compact + WRK:current + ciclos — 2026-07-13 en progreso. CP-03: Revision final CYCLE-04 — pendiente.

## §6: Blueprints (Índice)

_Índice breve de los Blueprints asignados a este ciclo. Se auto-pobla._

| BLP ID | Título | Estado | Prioridad | Objetivo | Gobernador |
|---|---|---|---|---|---|
| _BLP-NNN_ | _Título_ | _draft/ready/..._ | _critical/high/medium/low_ | _CYC-OBJ-N_ | _agente_ |


## §7: Estado y Métricas

**Estado actual:** draft
**Total Blueprints:** 0 | **Draft:** 0 | **Madurando:** 0 | **Ready:** 0 | **En Progreso:** 0 | **Done:** 0
**Progreso:** 0%
**Próximo punto de control:** _CP-NN — Fecha_
**Iniciado:** _YYYY-MM-DD_ | **Fin planificado:** _YYYY-MM-DD_


## §8: Reglas del Ciclo

1. No mezclar BLPs de dominios distintos en un mismo PR. 2. Siempre verificar runtime vs source vs build post-cambios. 3. Delegar ejecucion a Jarvis, verificacion a Heimdall.

## §9: Contrato de Calidad

| Compuerta | Estado |
|---|---|
| has_clear_purpose | ☐ |
| has_explicit_scope | ☐ |
| has_measurable_objectives | ☐ |
| has_operational_guidelines | ☐ |
| has_control_points | ☐ |
| aligns_with_project | ☐ |

> Todas las compuertas deben estar en ✅ antes de cycle.ready(). Ver blueprint-workflow skill, §4.1.
