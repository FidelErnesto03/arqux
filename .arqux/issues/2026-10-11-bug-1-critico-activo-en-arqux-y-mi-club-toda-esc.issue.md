# ISSUE: BUG-1 (critico, activo en ARQUX y mi_club): toda escritura con force=true (cortex_entry_add y cortex_entry_update) inyecta en el archivo .cortex una linea '$0:format{cortex:"0.1"}' mas un diccionario de sigilos (AUD:audit, ERR:error, FCS:focus, IDN:identity, KNW:knowledge, OBJ:objective, SES:session, WRK:work) dentro de $0. Consecuencia: E033_ZERO_SECTION_MEMORY_ENTRY x9 y E032 x6 permanentes, valid=false. Las entradas inyectadas son INALCANZABLES: cortex_entry_delete/update/move rechazan la seccion $0 ('Section $0 not found in doc'), cortex_entry_list $0 devuelve count=0 mientras cortex_verify reporta 9 (inconsistencia del parser), cortex_gc y cortex_migrate reseccionar no las tocan, y el selector por nombre exacto devuelve NOT_FOUND. ARQUX arrastra 12 E033 por esta causa; mi_club 9. Sin fix, todo proyecto que use force=true queda valid=false de forma permanente.
# Severity: medium | Status: verified | Handler: alfred | Date: 2026-10-11

## PROBLEM
BUG-1 (critico, activo en ARQUX y mi_club): toda escritura con force=true (cortex_entry_add y cortex_entry_update) inyecta en el archivo .cortex una linea '$0:format{cortex:"0.1"}' mas un diccionario de sigilos (AUD:audit, ERR:error, FCS:focus, IDN:identity, KNW:knowledge, OBJ:objective, SES:session, WRK:work) dentro de $0. Consecuencia: E033_ZERO_SECTION_MEMORY_ENTRY x9 y E032 x6 permanentes, valid=false. Las entradas inyectadas son INALCANZABLES: cortex_entry_delete/update/move rechazan la seccion $0 ('Section $0 not found in doc'), cortex_entry_list $0 devuelve count=0 mientras cortex_verify reporta 9 (inconsistencia del parser), cortex_gc y cortex_migrate reseccionar no las tocan, y el selector por nombre exacto devuelve NOT_FOUND. ARQUX arrastra 12 E033 por esta causa; mi_club 9. Sin fix, todo proyecto que use force=true queda valid=false de forma permanente.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T23:59:16Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Parcialmente corregido en 269d92c: _read_and_mutate pasaba atomic_write_json con strict=True implicito; ahora el CRUD escribe con strict=False y el dialecto rc1 solo lo emiten los handlers de migracion. ARQUX brain.cortex quedo limpio (E033 12 -> 0). RESIDUAL VIVO (verificado en sesion SES005): las entradas ya inyectadas en $0 siguen inalcanzables — entry.list $0 devuelve count=0 y entry.delete rechaza la seccion ('Section $0 not found'). Falta via de purga para archivos contaminados pre-fix. Baja de blocking a medium: no hay contaminacion nueva, pero la limpieza de archivos heredados sigue sin cobertura de handlers.

## UPDATE 2026-10-16

Residual cerrado: cortex.gc mode=purge_dialect (nuevo) elimina los artefactos rc1 inyectados en $0 a nivel texto — el $0:format y las declaraciones generadas que entry.list/delete no alcanzaban. dry_run por defecto, force=True aplica, INVALID_STATE si el archivo es rc1 genuino (sin glosario tabla-comentario). Verificado con archivo contaminado sintetico y guarda de rechazo. Accion pendiente de despliegue: purgar el '$0: format' residual del brain de ARQUX tras reiniciar el server MCP que sirve este repo (modulo viejo en memoria).
