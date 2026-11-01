# ISSUE: El hint de cortex.checkpoint anunciaba ';' como separador, pero el parser lo conserva dentro del valor: un checkpoint con ';' reportaba exito con obj, tasks y state vacios. El mensaje de ayuda indujo el error que decia prevenir.
# Severity: low | Status: verified | Handler: Alfred | Date: 2026-10-28

## PROBLEM
El hint de cortex.checkpoint anunciaba ';' como separador, pero el parser lo conserva dentro del valor: un checkpoint con ';' reportaba exito con obj, tasks y state vacios. El mensaje de ayuda indujo el error que decia prevenir.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-28T14:24:29Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-28

Corregido en 8168b78. El hint dice ahora: separadores ',' o newline; ';' se conserva dentro del valor. Test que verifica que el texto viejo ya no aparece.

## UPDATE 2026-10-28

Veredicto E-2046: verificado en vivo. Con ';' en el valor, el hint declara obj/tasks no parseados y explica que ';' se conserva en el valor.
