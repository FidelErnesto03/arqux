# ISSUE: [Hallazgo auditoria BLP-022 / F6] La separacion de deberes no se aplica tras identity.switch: actuando como heimdall (identidad auditor, contrato read-only LIM:no_mutation) se pudieron invocar handlers mutantes (evidence.record y issue.update) y persistir estado. El rol efectivo de permisos no cambia con el switch de identidad (o ctx.check no se aplica en el path MCP). Impacto: el auditor read-only puede mutar gobernanza; el modelo de separacion de deberes no se sostiene fuera del modelo de rol estatico. Esperado: identity.switch debe fijar/validar el rol efectivo del ctx (auditor -> denegar MUTATING_HANDLERS), o el server debe derivar el rol de la identidad activa.
# Severity: high | Status: verified | Handler: heimdall | Date: 2026-10-18

## PROBLEM
[Hallazgo auditoria BLP-022 / F6] La separacion de deberes no se aplica tras identity.switch: actuando como heimdall (identidad auditor, contrato read-only LIM:no_mutation) se pudieron invocar handlers mutantes (evidence.record y issue.update) y persistir estado. El rol efectivo de permisos no cambia con el switch de identidad (o ctx.check no se aplica en el path MCP). Impacto: el auditor read-only puede mutar gobernanza; el modelo de separacion de deberes no se sostiene fuera del modelo de rol estatico. Esperado: identity.switch debe fijar/validar el rol efectivo del ctx (auditor -> denegar MUTATING_HANDLERS), o el server debe derivar el rol de la identidad activa.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T19:03:38Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

FIXED (T-033): el rol efectivo sigue a la identidad activa. permissions.resolve_active_role/apply_active_identity_role + server._wrap_handler; ROLE_CONTROL_HANDLERS exento (identity.switch). Test test_active_identity_role_follows_the_switch. Requiere reiniciar el server para estar vivo.

## UPDATE 2026-10-22

VEREDICTO AUDITOR (Heimdall, read-only) 2026-10-22: CONFORME EN CODIGO, con salvedad de runtime. permissions.resolve_active_role/apply_active_identity_role (permissions.py:630/:650) y server._wrap_handler (server.py:54) derivan el rol efectivo de la identidad activa; test_active_identity_role_follows_the_switch pasa. HALLAZGO: el enforcement NO esta vivo en el server MCP actualmente conectado — dos sondeos ejecutados bajo la identidad heimdall (read-only) fueron ATENDIDOS en vez de denegados: issue.update -> OUT-ERROR NOT_FOUND (llego al handler) y task.create -> OUT-ERROR INVALID_ARGS (llego al handler). Coincide con la nota del fix ('requiere reiniciar el server para estar vivo'). ENDURECIMIENTO: reiniciar el server MCP y re-sondear; incorporar el reinicio como paso obligatorio del despliegue. Se marca verified condicionado a ese reinicio.

## UPDATE 2026-10-22

Verificado por verificacion del auditor Heimdall (ref E-1925). CONDICION OPERATIVA VIGENTE: el enforcement de rol efectivo no esta vivo en el server MCP actual; requiere reinicio del server y re-sondeo (Hallazgo registrado en E-1925). El codigo y el test estan conformes.
