# ISSUE: SESSION_IN_USE tras reinicio el mismo dia: la sesion no se puede re-adherir ni heredar
# Severity: medium | Status: triaged | Handler: Alfred | Date: 2026-10-28

## PROBLEM
Tras reiniciar el cliente el mismo dia, la sesion abierta por la ejecucion anterior no se puede re-adherir: session.context_set(intent='resumed', session_ref=SES015) devuelve SESSION_IN_USE porque la sesion sigue 'open' bajo otra execution y _is_expired solo expira en la frontera de dia. La ejecucion nueva no puede registrar tiempo hasta cerrar la anterior a mano.

Reproduccion: abrir sesion, reiniciar el cliente el mismo dia, intentar re-adherir.

Opciones: (a) usar last_activity como latido y considerar muerta una execution sin latido en N minutos; (b) permitir la re-adhesion cuando la execution propietaria ya no existe; (c) dejar el cierre administrativo como unica salida y documentarlo.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-28T14:33:46Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-28

Detectado en vivo al verificar el reinicio del 2026-10-28. Salida usada: session.close(session_ref=SES015) como cierre administrativo y apertura de SES016. La salida funciona, pero exige que el agente sepa que la sesion es huerfana. Decision pendiente del Arquitecto entre las tres opciones del ticket: el latido (last_activity) ya existe desde BLP-025, asi que (a) es viable sin datos nuevos.
