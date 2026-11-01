# ISSUE: blueprint.ac acumula notas FAIL bajo criterios ya verificados
# Severity: medium | Status: verified | Handler: Alfred (hallazgo en CODEC-CORTEX, sesiones SES001/SES002) | Date: 2026-11-01

## PROBLEM
## Sintoma
`blueprint.ac` agrega la nota de verificacion pero conserva las notas `FAIL` anteriores bajo el mismo criterio. El AC queda marcado `[x]` y, dos lineas abajo, dice `FAIL`. El registro se contradice a si mismo.

## Evidencia (CODEC-CORTEX, 2026-11-01)
- BLP-007 §12: AC-4, AC-5 y AC-6 quedaron con `[x]`, una nota `Verified` y debajo las notas `FAIL` de la medicion previa al port de Bash.
- La limpieza requirio reescribir §12 completo con `blueprint.update`; no existe un handler para retirar o marcar como historica una nota.
- El mismo patron aparece en BLP-006 AC-4 tras re-verificarse.

## Reproduccion
1. `blueprint.ac(ac_id=AC-4, status=failed, reason="...")`.
2. `blueprint.ac(ac_id=AC-4, status=verified, evidence="...")`.
3. `blueprint.read` §12: el AC muestra `[x]`, la nota Verified y la nota FAIL original.

## Esperado
- Al verificar un AC, las notas `FAIL` previas se marcan como historicas/superadas o se retiran del bloque activo.
- Debe existir una forma sancionada de limpiar notas sin reescribir la seccion entera.

## Actual
- Acumulacion append-only: el estado verificado y el FAIL conviven sin jerarquia.

## Impacto
El auditor y el Arquitecto leen evidencia contradictoria en un criterio ya cumplido. Baja la confianza en el registro y obliga a intervenciones manuales que pueden perder timestamps.

## Propuesta
- Semantica de supersesion en `blueprint.ac`: al pasar a `verified`, prefijar las notas FAIL con `[historica YYYY-MM-DD]` o moverlas a un bloque `## Historial`.
- Flag `supersede_previous=true` (default) y `keep_history=true`.
- Test que verifique que no queda un `FAIL:` sin marcar bajo un AC `[x]`.

## Criterios de aceptacion
- AC-1: tras `verified`, ninguna nota `FAIL:` queda sin marca historica.
- AC-2: la evidencia previa se conserva con timestamp.
- AC-3: test de regresion sobre el caso BLP-007 AC-4/5/6.

## CONTEXT
reported_by: Alfred
reported_at: 2026-11-01T20:09:54Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-11-01

Heimdall SIGNED-PASS audit 2.0: prior FAIL notes stamped superseded on verification (2623ea6)
