---
cycle_id: "CYCLE-02"
name: "CYCLE-02"
project_ref: ""
status: "ready"
governor: "hermes"
created_at: "2026-07-11T13:26:59Z"
updated_at: ""
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
matured_at: "2026-07-11T13:28:48Z"
matured_by: "hermes"
---


# Manifiesto: {name}

> Documento rector del ciclo. Define identidad, alcance, objetivos, directrices y puntos de control. Fuente de verdad para todos los Blueprints dentro de este ciclo.

---

## §1: Propósito

_¿Por qué existe este ciclo? ¿Qué problema aborda dentro del proyecto?_

**Relación con los objetivos del proyecto:**
_¿A qué objetivos del proyecto (desde brain.cortex OBJ) contribuye este ciclo?_


## §2: Alcance y Límites

**Dentro del alcance de este ciclo:**
- _Ítem 1_
- _Ítem 2_

**Fuera del alcance (excluido explícitamente):**
- _Ítem 1_
- _Ítem 2_

> Lo que está fuera del alcance NO debe ser abordado por ningún Blueprint de este ciclo.


## §3: Objetivos

_Objetivos concretos y medibles del ciclo. Cada Blueprint debe contribuir al menos a uno._

- [ ] **CYC-OBJ-1:** _Objetivo — criterio de éxito_
- [ ] **CYC-OBJ-2:** _Objetivo — criterio de éxito_
- [ ] **CYC-OBJ-3:** _Objetivo — criterio de éxito_


## §4: Directrices

_Directrices operacionales que rigen todos los Blueprints de este ciclo._

1. _Directriz 1 — ej., "Los Blueprints de infraestructura tienen prioridad sobre los de funcionalidad"_
2. _Directriz 2 — ej., "Todo Blueprint debe incluir un diagrama PUML en la sección de diseño"_
3. _Directriz 3 — ej., "Ningún Blueprint se cierra sin ejecutar todas las validaciones requeridas"_
4. _Directriz 4 — ej., "Las dependencias entre Blueprints deben resolverse antes de que el dependiente comience"_

**Directrices para creación de Blueprints:**
1. _Cada Blueprint debe referenciar el objetivo del ciclo al que contribuye_
2. _Los Blueprints críticos deben incluir un plan de reversión_
3. _Cada Blueprint debe estimar su impacto en los criterios de éxito del ciclo_


## §5: Puntos de Control

_Hitos, revisiones y puntos de validación. La ejecución se detiene en cada punto._

| ID | Tipo | Fecha Planificada | Descripción | Criterio de Aprobación |
|---|---|---|---|---|
| CP-01 | Revisión de Diseño | _YYYY-MM-DD_ | _Descripción_ | _¿Qué debe cumplirse?_ |
| CP-02 | Control Intermedio | _YYYY-MM-DD_ | _Descripción_ | _¿Qué debe cumplirse?_ |
| CP-03 | Revisión Final | _YYYY-MM-DD_ | _Descripción_ | _¿Qué debe validarse?_ |

> Los puntos de control son obligatorios. El gobernador debe informar al Arquitecto al aproximarse a uno.


## §6: Blueprints (Índice)

| BLP-001 | Ejecutar auditoría ejecutable de ArqUX siguiendo protocolo A... | done | medium | hermes |
| BLP-002 | Establecer pruebas automatizadas completas y pipeline CI/CD ... | done | medium | hermes |
| BLP-003 | Corregir pruebas de permisos contradictorios y mejorar cober... | done | medium | hermes |
| BLP-004 | Empaquetar correctamente los workflows y corregir el empaque... | done | medium | hermes |
| BLP-005 | Corregir los 9 tests que fallan en áreas críticas: blueprint... | done | medium | hermes |
| BLP-006 | Crear documentación automática de handlers (HANDLERS.md) gen... | ready | medium | hermes |
| BLP-007 | Corregir el error silencioso sync_brain sincronizando la pla... | done | medium | hermes |
| BLP-008 | Crear comando arqux quickstart para onboarding interactivo d... | done | medium | hermes |
| BLP-009 | Crear GETTING_STARTED.md como documentacion humana de ArqUX ... | done | medium | hermes |
| BLP-010 | Crear comando arqux status --dashboard con dashboard visual ... | done | medium | hermes |
| BLP-011 | Crear comandos arqux backup y arqux restore para respaldo y ... | done | medium | hermes |
| BLP-012 | Crear fixture de integracion arqux_env para tests de bluepri... | done | medium | hermes |
| BLP-013 | Refactorizar arquitectura de ArqUX en capas: core/models/han... | done | medium | hermes |
| BLP-014 | Aplicar ARQUX-PATCH-20260712 (v0.4.2 → 0.4.3) al repo /home/... | done | medium | alfred |
| BLP-015 | Corregir dos defectos de governance en los handlers MCP/core... | done | medium | alfred |
| BLP-016 | Formalizar el mecanismo de auto-gestión CORTEX-native: binde... | in_progress | medium | alfred |
| BLP-017 | Corregir blueprint.execute handler para que NO marque comple... | defined | medium | alfred |

## §7: Estado y Métricas

**Total Blueprints:** 17 | **Draft:** 0 | **Definido:** 1 | **Ready:** 1 | **En Progreso:** 1 | **Review:** 0 | **Done:** 14 | **Cancelado:** 0 | **Bloqueado:** 0
**Progreso:** 82%
**Total Tareas:** 6 | **Abiertas:** 6 | **Borrador:** 0 | **En Progreso:** 0 | **Completadas:** 0 | **Bloqueadas:** 0 | **Canceladas:** 0 | **Review:** 0

## §8: Reglas del Ciclo

_Reglas específicas de este ciclo._

1. _Regla 1_
2. _Regla 2_


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
