# ISSUE: El guard T-022 rechaza '_' como selector, pero el builder legacy del brain creo entradas con ese nombre exacto: el sistema no podia reparar las entradas que el mismo habia escrito (ni corregirlas ni borrarlas).
# Severity: medium | Status: verified | Handler: Alfred | Date: 2026-10-28

## PROBLEM
El guard T-022 rechaza '_' como selector, pero el builder legacy del brain creo entradas con ese nombre exacto: el sistema no podia reparar las entradas que el mismo habia escrito (ni corregirlas ni borrarlas).

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-28T14:24:41Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-28

Corregido en 5eff64a. force=True llega a la entrada exacta llamada '_'; sin force el rechazo de T-022 se mantiene. Tests en tests/test_t043_deprecated_name_repair.py (3 casos). Desbloquea la higiene del brain de EXPERTA, pendiente de reinicio del servidor para aplicarse.

## UPDATE 2026-10-28

Veredicto E-2046: verificado. delete/update de entradas '_' con force=true ejecutados contra el brain de EXPERTA.
