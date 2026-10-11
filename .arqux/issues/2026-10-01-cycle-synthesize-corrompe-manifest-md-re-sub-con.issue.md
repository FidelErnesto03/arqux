# ISSUE: cycle.synthesize corrompe MANIFEST.md: re.sub con repl de runtime — un backslash en el contenido de seccion lanza re.error o expande backrefs (a\1b). NUEVO-M1 de auditoria BLP-003 ronda 5; 3 sitios en cycle.py; corregido con lambda.
# Severity: high | Status: verified | Handler: alfred | Date: 2026-10-01

## PROBLEM
cycle.synthesize corrompe MANIFEST.md: re.sub con repl de runtime — un backslash en el contenido de seccion lanza re.error o expande backrefs (a\1b). NUEVO-M1 de auditoria BLP-003 ronda 5; 3 sitios en cycle.py; corregido con lambda.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-01T15:36:36Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-01

Corregido: los 3 sitios de cycle.py usan Pattern.sub(lambda _m: repl). Verificado por Heimdall ronda 6 (e2e: $4:{a\\1b}, {path C:\\Users\\nueva}, {x\\y} -> sin excepcion, texto literal en MANIFEST; marcador CYCLE:4 unico). tests/test_cycle_backslash.py. audit_ref=E-1022.
