# ISSUE: cortex.checkpoint acepta contenido vacio o parcial y borra WRK:current sin error
# Severity: blocking | Status: open | Handler: Alfred (hallazgo en CODEC-CORTEX, sesiones SES001/SES002) | Date: 2026-11-01

## PROBLEM
## Sintoma
`cortex.checkpoint` acepta contenido vacio, solo-espacios o con claves faltantes, devuelve exito y sobrescribe `WRK:current`. El estado de trabajo anterior se pierde y el siguiente agente arranca sin fcs/obj/tasks.

## Evidencia (CODEC-CORTEX, 2026-11-01)
- PULSE E_0108..E_0113 (14:15-14:52Z): seis checkpoints con `fcs=` y `obj=` vacios.
- `WRK:current` quedo vacio; el estado se reconstruyo desde PULSE, BLP-005/006/007 y git.
- Incidente relacionado E_2068 (checkpoint sin path resolvio otro proyecto), corregido en 1b679a7.
- El issue 2026-10-28-el-hint-de-cortex-checkpoint-anunciaba-como-sepa documento el separador `;`, pero el handler sigue aceptando claves no parseadas y escribe el resto en vez de fallar.

## Reproduccion
1. `cortex.checkpoint(path=PROJECT, content="fcs:prueba,obj:prueba,state:active")`.
2. `cortex.checkpoint(path=PROJECT, content="state:active")`.
3. `cortex.read` de la seccion 8: fcs y obj quedan vacios, sin error.
Variante: `content="fcs:a;obj:b;tasks:c;state:d"` -> solo persiste fcs; el resto se pierde con un hint posterior a la escritura.

## Esperado
- Rechazar contenido vacio o sin `fcs`/`obj` con INVALID_ARGS, sin escribir.
- En checkpoint parcial, conservar las claves ausentes (merge) en vez de limpiarlas.
- Si el parser no consume todas las claves, fallar antes de escribir.

## Actual
- Acepta y sobrescribe; el estado previo no es recuperable.
- Las claves no parseadas se ignoran con un hint posterior a la escritura.

## Impacto
Pérdida silenciosa de memoria de trabajo entre turnos y agentes. Contradice AXM:cortex_memory (WRK:current como unica fuente de verdad) y ya causo una reconstruccion manual completa en CODEC-CORTEX.

## Propuesta
- Validacion en el handler: content no vacio; `fcs` y `obj` obligatorios; merge de claves ausentes.
- Fail-fast si quedan claves sin parsear.
- Test de regresion que reproduzca E_0108..E_0113 y el caso `;`.

## Criterios de aceptacion
- AC-1: content vacio o solo `state` -> INVALID_ARGS, sin escritura.
- AC-2: checkpoint parcial conserva fcs/obj previos.
- AC-3: claves no parseadas -> error antes de escribir.
- AC-4: test cubre los tres casos y pasa en CI.

## CONTEXT
reported_by: Alfred
reported_at: 2026-11-01T20:09:38Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
