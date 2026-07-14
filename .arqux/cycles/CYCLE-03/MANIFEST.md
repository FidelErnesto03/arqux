---
cycle_id: "CYCLE-03"
name: "CORTEX-native: Implementacion de vision canales I/E/B y meta-handlers"
project_ref: "ARQUX"
status: "closed"
governor: "alfred"
created_at: "2026-07-11T17:57:01Z"
updated_at: "2026-07-12T18:00:00Z"
closed_at: "2026-07-13T16:48:45Z"
planned_start: "2026-07-12"
planned_end: ""
has_clear_purpose: "true"
has_explicit_scope: "true"
has_measurable_objectives: "true"
has_operational_guidelines: "true"
has_control_points: "true"
aligns_with_project: "true"
_template_ref: "CYCLE_MANIFEST_TEMPLATE.md"
matured_at: "2026-07-12T16:16:58Z"
matured_by: "alfred"
---




# Manifiesto: CORTEX-native — Implementacion de vision canales I/E/B y meta-handlers

> Documento rector del ciclo. Define identidad, alcance, objetivos, directrices y puntos de control.
> Fuente de verdad para todos los Blueprints dentro de este ciclo.

---

## §1: Propósito

Implementar la visión CORTEX-native documentada en `docs/reference/handlers-catalogo.hcortex.md`:
transformar los 73 handlers MCP de ArqUX para que operen de forma nativa en el canal I
(CORTEX denso entre agentes) con capacidad de modo E (HCORTEX para humanos).

Esto incluye:
- Corregir `cycle.mature()` para que valide quality gates antes de madurar (H-09).
- Añadir `mode=native` a `cortex.read` para que los agentes puedan leer CORTEX fielmente.
- Añadir `content` a 8 handlers con params descompuestos.
- Crear meta-handlers de fusión que agrupen secuencias de llamadas en 1.
- Simplificar `cortex.skill.md` delegando referencia a `cortex.ref`.
- Actualizar `mcp-handlers.skill.md` con firmas, canal y nuevos HDL.

**Relación con los objetivos del proyecto:**
Contribuye al objetivo de maduración de ArqUX como infraestructura de gobierno
universal: handlers más eficientes, formato CORTEX nativo como único conducto
de comunicación entre agentes, y validación de invariantes de estado.

---

## §2: Alcance y Límites

**Dentro del alcance de este ciclo:**
- P0.5: Arreglar `cycle.mature()` para leer y validar quality gates del manifiesto.
  Crear `cycle.validate()` como handler de inspección.
- P1: Implementar `cortex.ref(query)` con spec embebido (9 queries).
- P2-a: Añadir `mode=native` a `cortex.read`.
- P2-b: Añadir `content` a `cortex.entry.add` + `format=native` a `entry.get/list`.
- P3: Implementar `session.bootstrap()` (w00) y actualizar skills.
- P4: Añadir `content` a `identity.record`, `skill.record`, `session.context.set`,
  `session.close`, `task.create`, `blueprint.define`.
- P5: Implementar `cortex.patch` + `blueprint.synthesize`.
- P6: Implementar meta-handlers de flujo completo.
- P7: Utilidades restantes (`cortex.format`, promoción de `cortex.write`).
- Actualizar skills: `mcp-handlers.skill.md`, `workflows.skill.md`, `cortex.skill.md`.

**Fuera del alcance (excluido explícitamente):**
- Nuevos workflows w00–w11 (se documentan en docs/ pero no se integran al ciclo).
- Tests de integración del sistema completo (se hará en ciclo posterior).
- Migración de datos de ciclos anteriores.
- Implementación de `cortex.migrate` (diferido a ciclo futuro).
- Modificación de handlers de gates humanos (gate/ready/approve/ac/block).

> Lo que está fuera del alcance NO debe ser abordado por ningún Blueprint de este ciclo.

---

## §3: Objetivos

Objetivos concretos y medibles del ciclo. Cada Blueprint debe contribuir al menos a uno.

- [ ] **CYC-OBJ-1:** `cycle.mature()` valida quality gates ANTES de transicionar a ready.
      Criterio: `cycle.mature()` rechaza con error si alguna compuerta es false.
      Handler `cycle.validate()` existe y lista compuertas sin mutar.
- [ ] **CYC-OBJ-2:** 8 handlers existentes aceptan `content` CORTEX nativo + 3 handlers
      ganan `mode=native`/`format=native`. Criterio: todos los handlers del catálogo
      §5.4 pasan pruebas de aceptación con content y modo nativo.
- [ ] **CYC-OBJ-3:** 5 meta-handlers de fusión operativos (patch, synthesize, task.run,
      session.bootstrap, context.full). Criterio: cada meta-handler reduce la secuencia
      de llamadas del workflow correspondiente al valor documentado en §6.12.

---

## §4: Directrices

Directrices operacionales que rigen todos los Blueprints de este ciclo.

1. **Cada fase requiere su propio BLP.** No se agrupan fases en un mismo BLP.
   Un BLP por fase (P0.5, P1, P2-a, P2-b, P3, P4, P5, P6).
2. **Gates entre fases.** Ninguna fase comienza hasta que la anterior tenga
   `blueprint.approve` del Arquitecto. Sin excepción.
3. **Skills después del código.** Los skills se actualizan solo después de que el
   handler correspondiente esté implementado y verificado.
4. **Un handler por PR.** Cada fase genera exactamente un PR (o commit) con su handler
   y sus tests unitarios. Sin commits masivos.

**Directrices para creación de Blueprints:**
1. Cada BLP debe referenciar el objetivo del ciclo al que contribuye.
2. Cada BLP debe incluir un diagrama PUML de la secuencia optimizada.
3. Cada BLP debe estimar su impacto en las llamadas del workflow correspondiente.

---

## §5: Puntos de Control

Hitos, revisiones y puntos de validación. La ejecución se detiene en cada punto.

| ID | Tipo | Fecha Planificada | Descripción | Criterio de Aprobación |
|---|---|---|---|---|
| CP-01 | Revisión de Diseño | TBD | P0.5 completado: cycle.mature valida gates, cycle.validate existe | Arquitecto revisa y aprueba BLP-015 |
| CP-02 | Control Intermedio | TBD | P2 completo: cortex.read mode=native + content en entry.add/get/list | Pruebas de aceptación pasan, handlers responden en modo nativo |
| CP-03 | Revisión Final | TBD | P5-P6 completado: meta-handlers de fusión operativos | Reducciones de llamadas verificadas contra §6.12 |

> Los puntos de control son obligatorios. El gobernador debe informar al Arquitecto al aproximarse a uno.

---

## §6: Blueprints (Índice)

Índice breve de los Blueprints asignados a este ciclo. Se auto-pobla.

| BLP ID | Título | Estado | Prioridad | Objetivo | Gobernador |
|---|---|---|---|---|---|---|
| BLP-001 | README realignment (external agent) | `done` | medium | CYC-OBJ-2 | hermes |
| BLP-002 | Fix cycle.mature quality gates (H-09) | `cancelled` | critical | CYC-OBJ-1 | alfred |
| BLP-003 | P1: cortex.ref + cortex.format | `done` | critical | CYC-OBJ-2 | alfred |
| BLP-004 | P2-a: cortex.read mode=native | `done` | high | CYC-OBJ-2 | alfred |
| BLP-005 | P2-b: cortex.entry.add(content) + get/list format | `done` | high | CYC-OBJ-2 | alfred |
| BLP-006 | P3: context.detect + context.full + identity.get | `done` | high | CYC-OBJ-3 | alfred |
| BLP-007 | P5: blueprint.synthesize (w08 conversacional) | `done` | medium | CYC-OBJ-3 | alfred |
| BLP-008 | P3: session.bootstrap | `done` | high | CYC-OBJ-3 | alfred |
| BLP-009 | P4: content en 6 handlers existentes | `done` | high | CYC-OBJ-2 | alfred |
| BLP-010 | P6: meta-handlers (cortex.patch, task.run, skill.install, etc.) | `done` | medium | CYC-OBJ-3 | alfred |
| BLP-011 | P0.5: cycle.mature (duplicated by BLP-002) | `cancelled` | critical | CYC-OBJ-1 | hermes |
| BLP-012 | BLP-007a: Fix blueprint.define (absorbed by BLP-007) | `cancelled` | medium | CYC-OBJ-3 | alfred |
| BLP-013 | BLP-007b: Parser parse_blp_template() + skill | `done` | medium | CYC-OBJ-3 | alfred |

---

## §7: Estado y Métricas

**Estado actual:** done
**Total Blueprints:** 13 | **Done:** 9 | **Cancelled:** 4 | **Progreso:** 100%
**Iniciado:** 2026-07-12 | **Fin:** 2026-07-12
**Próximo punto de control:** CP-01 — P0.5 completado
**Iniciado:** 2026-07-12 | **Fin planificado:** TBD

---

## §8: Reglas del Ciclo

Reglas específicas de este ciclo.

1. **Prioridad estricta por fase.** No se salta ninguna fase. P0.5 va primero.
2. **Cada BLP debe incluir un plan de reversión.** Si el handler nuevo falla en producción,
   el sistema debe poder volver al comportamiento anterior sin pérdida de datos.
3. **No mezclar handler nuevo con handler modificado en el mismo BLP.**

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

> Todas las compuertas deben estar en ✅ antes de cycle.ready(). Ver blueprint-workflow skill, §4.1.
