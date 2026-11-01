# ISSUE: cycle.list ignoraba el filtro status: open y closed devolvian los mismos 14 ciclos, asi que el inventario por estado era inutil. El parametro se aceptaba y se descartaba sin avisar.
# Severity: medium | Status: verified | Handler: Alfred | Date: 2026-10-28

## PROBLEM
cycle.list ignoraba el filtro status: open y closed devolvian los mismos 14 ciclos, asi que el inventario por estado era inutil. El parametro se aceptaba y se descartaba sin avisar.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-28T14:24:28Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-28

Corregido en 8168b78. list_cycles lee el estado del manifiesto: closed solo si el manifiesto lo dice; draft y ciclos legados cuentan como abiertos. Tests en tests/test_t042_cycle_list_and_checkpoint_hint.py (6 casos). Verificado en vivo: open=[CYCLE-12], closed=13 ciclos.

## UPDATE 2026-10-28

Veredicto E-2046: verificado en vivo. open=[CYCLE-12], closed=13.
