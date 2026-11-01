# ISSUE: Blueprint acepta contenido en secciones incorrectas y blueprint.task no encuentra las tareas
# Severity: high | Status: open | Handler: Alfred (hallazgo en CODEC-CORTEX, sesiones SES001/SES002) | Date: 2026-11-01

## PROBLEM
## Sintoma
El flujo de sintesis acepta contenido en secciones que no le corresponden y el blueprint queda estructuralmente invalido. `blueprint.task` solo busca en §14, por lo que las tareas quedan invisibles para los handlers.

## Evidencia (CODEC-CORTEX, 2026-11-01)
- BLP-005 y BLP-006 se sintetizaron con las tareas T-5.x/T-6.x en §7 (Reglas Obligatorias), los riesgos en §9 (Diseno Operacional) y los criterios de aceptacion en §10 (Contratos).
- `blueprint.task(bp_id=BLP-006, task_id=T-6.2)` devolvio NOT_FOUND: "task T-6.2 not found in §14".
- La correccion requirio realinear a mano ocho secciones con `blueprint.update` (tareas a §14, riesgos a §15, ACs a §12).
- BLP-004, escrito de otra forma, si quedo bien formado; el defecto aparece en el camino de sintesis guiada.

## Reproduccion
1. Crear un BLP con `blueprint.synthesize`.
2. Volcar tareas con checkboxes en §7 y ACs en §10.
3. `blueprint.task` sobre una tarea existente -> NOT_FOUND.
4. `blueprint_ac` sobre un AC existente -> no lo encuentra.

## Esperado
- La guia de sintesis debe imponer el orden y el tipo de contenido por seccion (tareas §14, riesgos §15, ACs §12).
- `blueprint.update(section=N)` debe rechazar o advertir cuando el contenido no encaja con la seccion (p.ej. checkboxes de tarea en §7).
- Alternativa minima: `blueprint.task` y `blueprint.ac` buscan en todo el documento y reportan donde encontraron la tarea/AC.

## Actual
- Se acepta cualquier contenido en cualquier seccion.
- Los handlers de tareas/ACs fallan con NOT_FOUND sin explicar la causa estructural.

## Impacto
Blueprints con secciones cruzadas: el ejecutor no puede marcar tareas, el auditor lee riesgos donde deberia leer diseno y la compuerta de cierre queda en un documento mal formado. Ocurrio en 2 de 3 BLPs creados ese dia.

## Propuesta
- Validacion semantica por seccion en `blueprint.update` (checkboxes solo en §14, ACs con AC-xx en §12, tabla de riesgos en §15).
- `blueprint.synthesize` devuelve el `next_section` con el tipo esperado y rechaza saltos.
- Busqueda global en `blueprint.task`/`blueprint.ac` con seccion de origen en el error.

## Criterios de aceptacion
- AC-1: contenido de tareas en §7 -> INVALID_ARGS o warning con la seccion correcta.
- AC-2: `blueprint.task` encuentra tareas aunque esten fuera de §14, o el error indica donde estan.
- AC-3: test de regresion con un BLP sintetizado en desorden.

## CONTEXT
reported_by: Alfred
reported_at: 2026-11-01T20:09:47Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
