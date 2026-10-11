# ISSUE: Dos desvios de baja severidad entre la CI y el informe de release. (a) Umbral laxo: el paso 'Validate handlers count' de .github/workflows/ci.yml comprueba 'test "$COUNT" -ge 73', pero la superficie real es de 97 handlers (verificado con 'uv tool run arqux handlers | wc -l' y con scripts/check_surfaces.py, que reporta handlers=97). El umbral quedo 24 handlers por debajo de la realidad y no protegeria contra una regresion que borrara hasta 24 handlers. Deberia fijarse desde la superficie declarada, no como constante manual. (b) Informe desalineado: docs/release/0.9.0-report.md §1 documenta 4 blueprints (BLP-001 a BLP-004) mientras CYCLE-13 cerro 6 (BLP-005 y BLP-006 completados despues y no figures en el informe). En el mismo eje, el registro de ciclos via MCP cycle_current reporta abiertos CYCLE-11 y CYCLE-12, y ninguno de los dos es CYCLE-13, que figura closed en .arqux/cycles/CYCLE-13/cycle.cortex; meta-brain DOM:arqux declara ademas cycle:'CYCLE-11' con cycle_status:'completed'. Ninguno de estos pasos de CI se ha ejecutado jamas, porque el error de coleccion de tests/test_voice.py interrumpe el paso de pytest previo.
# Severity: low | Status: open | Handler: alfred | Date: 2026-10-11

## PROBLEM
Dos desvios de baja severidad entre la CI y el informe de release. (a) Umbral laxo: el paso 'Validate handlers count' de .github/workflows/ci.yml comprueba 'test "$COUNT" -ge 73', pero la superficie real es de 97 handlers (verificado con 'uv tool run arqux handlers | wc -l' y con scripts/check_surfaces.py, que reporta handlers=97). El umbral quedo 24 handlers por debajo de la realidad y no protegeria contra una regresion que borrara hasta 24 handlers. Deberia fijarse desde la superficie declarada, no como constante manual. (b) Informe desalineado: docs/release/0.9.0-report.md §1 documenta 4 blueprints (BLP-001 a BLP-004) mientras CYCLE-13 cerro 6 (BLP-005 y BLP-006 completados despues y no figures en el informe). En el mismo eje, el registro de ciclos via MCP cycle_current reporta abiertos CYCLE-11 y CYCLE-12, y ninguno de los dos es CYCLE-13, que figura closed en .arqux/cycles/CYCLE-13/cycle.cortex; meta-brain DOM:arqux declara ademas cycle:'CYCLE-11' con cycle_status:'completed'. Ninguno de estos pasos de CI se ha ejecutado jamas, porque el error de coleccion de tests/test_voice.py interrumpe el paso de pytest previo.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T17:59:11Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
