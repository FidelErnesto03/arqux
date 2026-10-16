# ISSUE: Auditoría Heimdall de BLP-005 (CYCLE-13) detectó HD-01 CRÍTICO: la precondición P-03 afirmaba que task.run era un ejecutor real, pero el código muestra el mismo defecto (cadena literal 'executed', literal 'assumed_met', y 'outcome = complete' incondicional). Además se confirmó que NO existe ningún mecanismo de ejecución en ArqUX (cero subprocess/Popen/os.system/shutil.which en src/arqux/handlers/). Alfred amplió BLP-005 de 2 correcciones a construcción del ejecutor + corrección de 2 handlers. Requiere segunda auditoría antes de claim, y requiere aprobación de alcance del Arquitecto (P-08) porque construir capacidad de ejecución es más amplio que corregir dos handlers.
# Severity: high | Status: verified | Handler: alfred | Date: 2026-10-10

## PROBLEM
Auditoría Heimdall de BLP-005 (CYCLE-13) detectó HD-01 CRÍTICO: la precondición P-03 afirmaba que task.run era un ejecutor real, pero el código muestra el mismo defecto (cadena literal 'executed', literal 'assumed_met', y 'outcome = complete' incondicional). Además se confirmó que NO existe ningún mecanismo de ejecución en ArqUX (cero subprocess/Popen/os.system/shutil.which en src/arqux/handlers/). Alfred amplió BLP-005 de 2 correcciones a construcción del ejecutor + corrección de 2 handlers. Requiere segunda auditoría antes de claim, y requiere aprobación de alcance del Arquitecto (P-08) porque construir capacidad de ejecución es más amplio que corregir dos handlers.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-10T22:05:30Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Implementado en BLP-005: existe src/arqux/handlers/execution.py — ejecutor real con deny-by-default (ALLOWED_ACTIONS), outcome con evidence_ref obligatorio, actor+role propagados, sin shell. task.run (handlers/task.py ~L760) enruta cada paso via marcador [exec:action k=v] hacia execute_action; el outcome sigue a la ejecucion (complete solo si todos los pasos executed con evidencia; fail con razon). Pasos sin spec -> unavailable, no 'executed'. 140 tests de ejecucion en verde. HD-01 cerrado en codigo; el pase a 'verified' requiere la segunda auditoria de Heimdall con audit_ref (condicion del propio issue).
