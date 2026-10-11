# ISSUE: El gate de release exige delta = 0 contra la linea base fijada (docs/release/regression-baseline.json, policy BLP-004 §7.6/§13) y el delta real es +1. Medicion de hoy (2026-10-11, python3 -m pytest -q, 21.4 s): 2035 passed / 16 failed / 2 skipped. La linea base declara 15 fallos conocidos y los 15 se reproducen exactamente. El 16 es tests/test_host_bridge.py::test_host_bridge_brokers_current_session_response, ausente de la linea base y NO DETERMINISTA: 3 corridas aisladas dieron passed / failed / passed. Causa: carrera entre el hilo de submit y el poll inmediato en test_host_bridge.py lineas 59-67, sobre SocketCurrentAgentAdapter. No es una regresion funcional sino un test no reproducible, pero un gate cuyo veredicto depende de una moneda al aire no es un gate. El informe docs/release/0.9.0-report.md §9 declara la condicion 'Suite sin regresiones vs baseline' en verde. Fix: sincronizar el arranque del hilo de submit con la disponibilidad de la peticion en el test (o exercise deterministico del adaptador), y re-fijar la linea base con la cifra real una vez la suite sea ejecutable en CI.
# Severity: high | Status: open | Handler: alfred | Date: 2026-10-11

## PROBLEM
El gate de release exige delta = 0 contra la linea base fijada (docs/release/regression-baseline.json, policy BLP-004 §7.6/§13) y el delta real es +1. Medicion de hoy (2026-10-11, python3 -m pytest -q, 21.4 s): 2035 passed / 16 failed / 2 skipped. La linea base declara 15 fallos conocidos y los 15 se reproducen exactamente. El 16 es tests/test_host_bridge.py::test_host_bridge_brokers_current_session_response, ausente de la linea base y NO DETERMINISTA: 3 corridas aisladas dieron passed / failed / passed. Causa: carrera entre el hilo de submit y el poll inmediato en test_host_bridge.py lineas 59-67, sobre SocketCurrentAgentAdapter. No es una regresion funcional sino un test no reproducible, pero un gate cuyo veredicto depende de una moneda al aire no es un gate. El informe docs/release/0.9.0-report.md §9 declara la condicion 'Suite sin regresiones vs baseline' en verde. Fix: sincronizar el arranque del hilo de submit con la disponibilidad de la peticion en el test (o exercise deterministico del adaptador), y re-fijar la linea base con la cifra real una vez la suite sea ejecutable en CI.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T17:54:53Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
