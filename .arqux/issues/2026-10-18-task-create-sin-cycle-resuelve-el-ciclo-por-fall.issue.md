# ISSUE: task.create sin cycle= resuelve el ciclo por fallback al ULTIMO directorio de cycles (CYCLE-14, CERRADO) e ignora el ciclo de contexto/sesion (CYCLE-12). Reproducido en vivo (SES009): 4 task.create sin cycle= crearon T-011..T-014 en ARQUX/.arqux/cycles/CYCLE-14/tasks (manifest status: closed). Es el mismo patron que E-1816 (blueprint.synthesize) pero en task.create, que NO fue cubierto por BLP-022 (§6 alcance cerrado; §16.4: un handler mas con el mismo defecto se registra como issue). Codigo: create_task en handlers/task.py, rama else -> current_cycle(); si _cc.data no trae open_cycles, usa open_cycles[-1] que es 'todas las carpetas ordenadas', no las abiertas. Esperado: respetar el ciclo activo/contexto y rechazar crear en un ciclo cerrado (CYCLE_CLOSED).
# Severity: medium | Status: verified | Handler: alfred | Date: 2026-10-18

## PROBLEM
task.create sin cycle= resuelve el ciclo por fallback al ULTIMO directorio de cycles (CYCLE-14, CERRADO) e ignora el ciclo de contexto/sesion (CYCLE-12). Reproducido en vivo (SES009): 4 task.create sin cycle= crearon T-011..T-014 en ARQUX/.arqux/cycles/CYCLE-14/tasks (manifest status: closed). Es el mismo patron que E-1816 (blueprint.synthesize) pero en task.create, que NO fue cubierto por BLP-022 (§6 alcance cerrado; §16.4: un handler mas con el mismo defecto se registra como issue). Codigo: create_task en handlers/task.py, rama else -> current_cycle(); si _cc.data no trae open_cycles, usa open_cycles[-1] que es 'todas las carpetas ordenadas', no las abiertas. Esperado: respetar el ciclo activo/contexto y rechazar crear en un ciclo cerrado (CYCLE_CLOSED).

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T20:16:05Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

FIXED (T-037): create_task resuelve el ciclo = explicito > ciclos ABIERTOS via current_cycle (antes leia _cc.data, inexistente en CortexOUT -> _open vacio -> fallback al ultimo DIRECTORIO, cerrado) > ultimo ciclo abierto; y llama require_open_cycle -> CYCLE_CLOSED. Tests: test_task_create_rejects_a_closed_cycle / test_task_create_prefers_the_open_cycle. Suite 2419 passed / 0 failed.

## UPDATE 2026-10-22

VEREDICTO AUDITOR (Heimdall, read-only) 2026-10-22: CONFORME. handlers/task.py:137 llama require_open_cycle y :115 importa cycle_is_closed; el ciclo se resuelve explicito > abiertos (via current_cycle) > ultimo abierto, y el cerrado se rechaza con CYCLE_CLOSED (ya no cae al ultimo directorio). Tests test_task_create_rejects_a_closed_cycle y test_task_create_prefers_the_open_cycle pasan. Sin hallazgos. Se marca verified.

## UPDATE 2026-10-22

Verificado por verificacion del auditor Heimdall (ref E-1926). Cerrado.
