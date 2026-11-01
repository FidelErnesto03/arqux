# ISSUE: [Hallazgo auditoria BLP-022 / F5] require_open_cycle no cubre el fallback de blueprint.synthesize: cuando no hay cycle= explicito ni FCS:current en el brain, _resolve_target_cycle devuelve None, require_open_cycle(None) no juzga, y _find_or_create_blueprint cae al fallback 'ultimo ciclo abierto' o 'CYCLE-01' sin validar cierre. Escenario: proyecto sin FCS y CYCLE-01 cerrado -> synthesize podria crear en un ciclo cerrado. Esperado: validar el cierre del ciclo resuelto por CUALQUIER camino (incluido el fallback).
# Severity: low | Status: verified | Handler: heimdall | Date: 2026-10-18

## PROBLEM
[Hallazgo auditoria BLP-022 / F5] require_open_cycle no cubre el fallback de blueprint.synthesize: cuando no hay cycle= explicito ni FCS:current en el brain, _resolve_target_cycle devuelve None, require_open_cycle(None) no juzga, y _find_or_create_blueprint cae al fallback 'ultimo ciclo abierto' o 'CYCLE-01' sin validar cierre. Escenario: proyecto sin FCS y CYCLE-01 cerrado -> synthesize podria crear en un ciclo cerrado. Esperado: validar el cierre del ciclo resuelto por CUALQUIER camino (incluido el fallback).

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T19:03:39Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

FIXED (T-034): cycle_is_closed() + _resolve_target_cycle cubre el fallback (ultimo ciclo abierto, o el ultimo directorio -> require_open_cycle rechaza). Tests test_synthesize_never_falls_back_into_a_closed_cycle / test_synthesize_fallback_picks_the_open_cycle.

## UPDATE 2026-10-22

VEREDICTO AUDITOR (Heimdall, read-only) 2026-10-22: CONFORME. blueprint/synthesize.py:190 _resolve_target_cycle devuelve el ciclo resuelto por cualquier camino (incluido el fallback) y :124 require_open_cycle lo juzga; el fallback ya no puede crear en un ciclo cerrado. Tests test_synthesize_never_falls_back_into_a_closed_cycle y test_synthesize_fallback_picks_the_open_cycle pasan. Sin hallazgos. Se marca verified.

## UPDATE 2026-10-22

Verificado por verificacion del auditor Heimdall (ref E-1924). Cerrado.
