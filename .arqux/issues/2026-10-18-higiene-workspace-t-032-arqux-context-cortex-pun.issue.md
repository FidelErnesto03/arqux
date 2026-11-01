# ISSUE: [Higiene workspace T-032] .arqux/context.cortex (puntero de contexto de sesion del workspace) se escribe con el sigil CTX, que NO esta declarado en su glosario local ($0 vacio, sigil_count=0): el parser lo reporta como E017_UNPARSED_LINE (0 entradas reconocidas). Los handlers de sesion lo leen con su propio parser, por lo que funciona hoy, pero el archivo es invisible/invalido para CODEC-CORTEX: no participa de verify, gc, reconciliacion ni render, y no aparece en ningun chequeo de salud. Contenido actual: 'CTX:Alfred project="ARQUX" scope="CYCLE-12" agent="Alfred" ses="SES006" project_root="/home/vatrox/workspace/ARQUX"'. Esperado: declarar CTX en el glosario $0 (o migrar a una entrada canonica, p.ej. SES/CTX declarado) para que el puntero sea machine-readable y auditable.
# Severity: medium | Status: fixed | Handler: Alfred | Date: 2026-10-18

## PROBLEM
[Higiene workspace T-032] .arqux/context.cortex (puntero de contexto de sesion del workspace) se escribe con el sigil CTX, que NO esta declarado en su glosario local ($0 vacio, sigil_count=0): el parser lo reporta como E017_UNPARSED_LINE (0 entradas reconocidas). Los handlers de sesion lo leen con su propio parser, por lo que funciona hoy, pero el archivo es invisible/invalido para CODEC-CORTEX: no participa de verify, gc, reconciliacion ni render, y no aparece en ningun chequeo de salud. Contenido actual: 'CTX:Alfred project="ARQUX" scope="CYCLE-12" agent="Alfred" ses="SES006" project_root="/home/vatrox/workspace/ARQUX"'. Esperado: declarar CTX en el glosario $0 (o migrar a una entrada canonica, p.ej. SES/CTX declarado) para que el puntero sea machine-readable y auditable.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T18:17:14Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

Triageado: puntero de sesion no machine-readable (CTX sin declarar). Fix acotado (declarar CTX en $0 o migrar a entrada canonica).

## UPDATE 2026-10-23

Fixed (T-040): context.cortex ahora se escribe canónico — glosario $0 declara el sigil CTX y la entrada usa sintaxis attrs CTX:<agent>{name,project,scope,blp?,agent,ses?,project_root}, parseable por CODEC-CORTEX (verificado: 0 E017, sigil_count=1). Lectores dual-formato (canónico + legacy k="v") en context_get, _project.find_project_root, checkpoint, _update_context_agent y response hooks; escritura centralizada en _context_document (session.py, reusada por identity.switch). Tests: 2481 pass. El archivo runtime migra a canónico en la próxima escritura tras reiniciar el servidor MCP.
