# ISSUE: Los handlers de sesion escriben entradas SES incompletas en brain.cortex: cortex_verify reporta E032_CRITICAL_SIGIL_INCOMPLETE sobre SES001-SES005 (missing required fields ['input','output','outcome']), lo que mantiene el brain en valid=false pese al shim de dialecto de 26f0ec3. Confirmado en vivo (SES005, 2026-10-16): la SES creada hoy por session.context.set ya salio incompleta, asi que no es solo deuda de entradas viejas — el escritor actual de SES (session.context.set/session.close, handlers/session.py) no emite input/output/outcome. Impacto: valid=false permanente en todo proyecto con sesiones, y el gate de verificacion vuelve a ser ruido. Verificar si los campos deben completarse al cierre (session.close captura el cierre desde 91f4de1) o si la plantilla SES requiere relajar el requisito.
# Severity: medium | Status: verified | Handler: alfred | Date: 2026-10-16

## PROBLEM
Los handlers de sesion escriben entradas SES incompletas en brain.cortex: cortex_verify reporta E032_CRITICAL_SIGIL_INCOMPLETE sobre SES001-SES005 (missing required fields ['input','output','outcome']), lo que mantiene el brain en valid=false pese al shim de dialecto de 26f0ec3. Confirmado en vivo (SES005, 2026-10-16): la SES creada hoy por session.context.set ya salio incompleta, asi que no es solo deuda de entradas viejas — el escritor actual de SES (session.context.set/session.close, handlers/session.py) no emite input/output/outcome. Impacto: valid=false permanente en todo proyecto con sesiones, y el gate de verificacion vuelve a ser ruido. Verificar si los campos deben completarse al cierre (session.close captura el cierre desde 91f4de1) o si la plantilla SES requiere relajar el requisito.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-16T14:24:14Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Resuelto: los campos del contrato SES del codec (input/output/outcome, no vacios por E034) se escriben en los tres puntos de mutacion de session_identity.py (open, reopen, close). Las 5 SES heredadas del brain de ARQUX reparadas; cortex_verify valid=true. Entradas heredadas en otros proyectos se reparan igual o al primer reopen/close. Pendiente verified por auditoria.
