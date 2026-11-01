# ISSUE: Nombres de parametros y errores inconsistentes entre handlers
# Severity: low | Status: open | Handler: Alfred (hallazgo en CODEC-CORTEX, sesiones SES001/SES002) | Date: 2026-11-01

## PROBLEM
## Sintoma
Handlers de la misma familia usan nombres distintos para el mismo concepto y devuelven errores crudos de Python en vez de INVALID_ARGS. Cada error cuesta una llamada y, en automatizacion, induce reintentos equivocados.

## Evidencia (CODEC-CORTEX, 2026-11-01)
- `timelog.query(session="SES001")` -> `TypeError: query_handler() got an unexpected keyword argument 'session'`; el parametro correcto es `session_ref`.
- `blueprint.read(blueprint_id="BLP-006")` -> `'bp_id' is a required property`; el schema usa `bp_id`.
- `cortex.entry.get(section="$4", name="SES001")` -> `'selector' is a required property`; el handler exige `selector`.
- `cortex.read(path=<project_dir>)` -> `READ_ERROR [Errno 21] Is a directory`; el handler espera el archivo `.cortex`, no el proyecto.

## Reproduccion
Llamar cada handler con el nombre "natural" del concepto (session, blueprint_id, section/name, project_dir) y observar el error.

## Esperado
- Alias aceptados (`session`/`session_ref`, `blueprint_id`/`bp_id`, `section+name`/`selector`, `project`/`file`).
- Errores `INVALID_ARGS` con el parametro esperado y un ejemplo de llamada.
- `cortex.read` distingue proyecto vs archivo y resuelve `<project>/.arqux/brain.cortex`.

## Actual
- Nombres mezclados y `TypeError`/mensajes de sistema de archivos sin traduccion.

## Impacto
Friccion de uso y consumo de tokens/tiempo; los agentes aprenden la API por prueba y error. Afecta especialmente a la automatizacion multiagente.

## Propuesta
- Capa de normalizacion de argumentos con alias declarados en el schema.
- Validacion temprana con `INVALID_ARGS: expected bp_id (alias blueprint_id)`.
- `cortex.read` acepta proyecto o archivo.

## Criterios de aceptacion
- AC-1: los alias listados funcionan o el error nombra el parametro correcto.
- AC-2: ningun handler devuelve `TypeError` crudo.
- AC-3: `cortex.read(project)` resuelve el brain del proyecto.

## CONTEXT
reported_by: Alfred
reported_at: 2026-11-01T20:10:14Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
