# ISSUE: Meta-brain del workspace (.arqux/meta-brain.cortex, 37 entries) contiene entradas DOM duplicadas con metricas en conflicto: Manhattan (DOM:manhattan_0001_0005 blueprints_done:11 vs DOM:manhattan blueprints_done:21), mi_club (sin cycle vs DOM:mi_club blueprints_done:14), LOCAL (DOM:local_0002 vs DOM:local), ENVX_EXEC (DOM:envx_exec path relativo vs DOM:ENVX_EXEC path vacio). Total 4 pares duplicados. Impacto: workspace_status --dashboard degrada, sync.reconcile puede aplicar metricas de la entrada equivocada, y el conteo de proyectos (14) no es confiable. Nota: issue.create no acepta workspace root (correcto por AXM:no_workspace_project) — se registra en ARQUX por ser defecto del framework.
# Severity: high | Status: fixed | Handler: alfred | Date: 2026-10-08

## PROBLEM
Meta-brain del workspace (.arqux/meta-brain.cortex, 37 entries) contiene entradas DOM duplicadas con metricas en conflicto: Manhattan (DOM:manhattan_0001_0005 blueprints_done:11 vs DOM:manhattan blueprints_done:21), mi_club (sin cycle vs DOM:mi_club blueprints_done:14), LOCAL (DOM:local_0002 vs DOM:local), ENVX_EXEC (DOM:envx_exec path relativo vs DOM:ENVX_EXEC path vacio). Total 4 pares duplicados. Impacto: workspace_status --dashboard degrada, sync.reconcile puede aplicar metricas de la entrada equivocada, y el conteo de proyectos (14) no es confiable. Nota: issue.create no acepta workspace root (correcto por AXM:no_workspace_project) — se registra en ARQUX por ser defecto del framework.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-08T14:27:36Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-10

Triaje 2026-10-10: confirmado vía cortex.entry.get sobre /home/vatrox/workspace/.arqux/meta-brain.cortex: DOM:* devuelve 22 entradas y reproduce los 4 pares duplicados reportados (Manhattan, mi_club, LOCAL, ENVX_EXEC), con métricas conflictivas. Causa probable: coexistencia de entradas históricas y nuevas generadas por sincronizaciones/reconciliaciones sin una clave canónica única; la causa exacta de cada par aún debe auditarse. Ruta de corrección: BLP formal en ARQUX para definir canonización por path+name, seleccionar la entrada más completa/reciente, deduplicar mediante handlers CORTEX, validar el brain y repetir workspace_status; no ejecutar sync_run hasta fijar la regla de canon.

## UPDATE 2026-10-10

Resuelto end-to-end. sync.py ahora canoniza DOM semánticamente por nombre, conserva la fila más completa/reciente, fusiona atributos faltantes y elimina duplicados de forma idempotente; reconcile_brain expone meta_deduplication. Se reparó el meta-brain vivo mediante handlers CORTEX: desaparecieron los cuatro pares reportados y la entrada espuria DOM:workspace; workspace_status devuelve Meta-brain OK y Health 4 pass, 0 fail, 0 warn. Evidencia técnica: PYTHONPATH=src python -m pytest -q => 1882 passed, 16 skipped. Validación viva posterior: DOM:* count=19, una sola entrada canónica por cada par reportado.
