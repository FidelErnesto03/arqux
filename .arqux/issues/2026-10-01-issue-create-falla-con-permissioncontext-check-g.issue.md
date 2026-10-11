# ISSUE: issue.create falla con "PermissionContext.check() got multiple values for argument 'handler'" cuando se pasa el parametro handler por MCP; sin handler funciona. Bug de firma/llamada en handlers/issue.py create_issue.
# Severity: low | Status: verified | Handler: alfred | Date: 2026-10-01

## PROBLEM
issue.create falla con "PermissionContext.check() got multiple values for argument 'handler'" cuando se pasa el parametro handler por MCP; sin handler funciona. Bug de firma/llamada en handlers/issue.py create_issue.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-01T15:36:54Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-01

Corregido: PermissionContext.check/can renombran su primer parametro a handler_name, evitando la colision con un kwarg de llamada llamado 'handler' (issue.create). Verificado: tests/test_check_handler_kwarg.py (3) + suite 1818 passed; validacion live en el uv tool OK. audit_ref=E-1028.
