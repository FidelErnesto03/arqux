# ISSUE: El scope de la sesion no sigue al BLP activo tras blueprint.ready/claim
# Severity: medium | Status: verified | Handler: Alfred (hallazgo en CODEC-CORTEX, sesiones SES001/SES002) | Date: 2026-11-01

## PROBLEM
## Sintoma
El scope de la sesion queda congelado en el BLP con el que se abrio y no sigue al BLP que realmente se esta ejecutando. El trabajo se atribuye al BLP equivocado hasta que alguien re-apunta la sesion a mano.

## Evidencia (CODEC-CORTEX, 2026-11-01)
- SES001 se abrio a las 13:49Z con scope `CYCLE-03/BLP-004`.
- A las 16:02Z se creo BLP-006 y el trabajo real paso a ese BLP (fix de fences, certificado 141/141).
- A las 18:19Z `session.status` seguia devolviendo `scope=CYCLE-03/BLP-004`; hubo que llamar `session.context.set(intent=resumed, session_ref=SES001, blp=BLP-006)` para corregirlo.
- El timelog y los eventos de la sesion quedaron bajo un scope que no correspondia al trabajo.

## Reproduccion
1. `session.context.set(project, scope=CYCLE-03, blp=BLP-004)`.
2. `blueprint.ready(BLP-006)` + `blueprint.claim(BLP-006)`.
3. `session.status`: el scope sigue en BLP-004.

## Esperado
- `blueprint.ready`/`blueprint.claim` sincronizan el scope de la sesion activa con el BLP, o emiten un warning/evento de divergencia.
- `session.status` deberia marcar `stale_scope=true` cuando el BLP activo del proyecto no coincide con el de la sesion.

## Actual
- El puntero de sesion es independiente del ciclo de vida del BLP; no hay deteccion de divergencia.

## Impacto
Atribucion erronea de tiempo y evidencia; el auditor puede reconstruir mal que BLP produjo que cambio. Riesgo de que dos BLPs se mezclen en el mismo registro de sesion.

## Propuesta
- Hook en `blueprint.ready/claim/complete` que actualice el scope de la sesion activa (mismo proyecto) o registre `scope_drift`.
- Campo `stale_scope` en `session.status` y aviso en `session.resume`.
- Test con dos BLPs en la misma sesion.

## Criterios de aceptacion
- AC-1: tras `claim`, el scope de la sesion apunta al BLP reclamado.
- AC-2: si no se puede actualizar, se emite un evento de divergencia visible.
- AC-3: test de regresion con BLP-004 -> BLP-006.

## CONTEXT
reported_by: Alfred
reported_at: 2026-11-01T20:10:07Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-11-01

Heimdall SIGNED-PASS audit 2.0: ready/claim sync session context blp, stale_scope reported (09ef86e)
