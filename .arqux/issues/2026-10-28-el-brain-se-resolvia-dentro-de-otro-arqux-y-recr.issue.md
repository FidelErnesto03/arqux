# ISSUE: El brain se resolvia dentro de otro .arqux y recreaba el arbol anidado en cada operacion: el doctor lo reportaba como FAIL y no era residuo viejo sino un defecto de resolucion de rutas.
# Severity: medium | Status: verified | Handler: Alfred | Date: 2026-10-28

## PROBLEM
El brain se resolvia dentro de otro .arqux y recreaba el arbol anidado en cada operacion: el doctor lo reportaba como FAIL y no era residuo viejo sino un defecto de resolucion de rutas.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-28T14:24:29Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-28

Corregido en 4ad8263. session_identity.brain_path y pulse._brain_cortex_path reconocen un .arqux como destino final y no le añaden otro. El arbol anidado se archivo en .arqux/archive/hygiene-2026-10-28/. Doctor: 7 pass, 0 fail, 0 warn. Tests en tests/test_t044_no_nested_arqux_resolution.py (4 casos).

## UPDATE 2026-10-28

Veredicto E-2046: verificado. Doctor 7 pass, 0 fail, 0 warn; el arbol no se regenera tras el reinicio.
