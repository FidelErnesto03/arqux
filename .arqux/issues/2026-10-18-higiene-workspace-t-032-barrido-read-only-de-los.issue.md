# ISSUE: [Higiene workspace T-032] Barrido read-only de los 15 cerebros de proyecto (codec-cortex parse+validate): 497 errores en 12 de 15. ENVX_MCP 286 (263 E008 duplicados + 23 E032) | Manhattan 92 (45 E034 + 39 E032 + 8 E008) | Conquistadores 65 (55 E032 + 10 E034) | Banco Familiar 16 (14 E032 + 2 E008) | mi_club 15 (9 E033 entradas operativas en $0 + 6 E032) | ENVX_OPER 6 (5 E006 + 19 I001) | ARQUX 4 (E032) | Manhattan/BEX 4 (2 E006) | ENVX_EXEC 3 | ENVX_INFRA 3 | CODEC-CORTEX 2 | ENVX 1 | LOCAL/DEX/NEX 0. Las 6 identidades restantes (auditor/executor/governor/heimdall/jarvis/seshat) estan limpias. GAP: migrate_cortex_file (w11) se niega si el archivo valida y no completa campos requeridos vacios ('does NOT fabricate missing semantic fields'), asi que E032/E034 quedan sin ruta automatica; y E008 requiere cortex.gc por archivo. Esperado: una ruta de remediacion gobernada por proyecto (BLP) que distinga dedupe automatico (E008) de completado de campos (que exige criterio humano/evidencia, no fabricacion).
# Severity: medium | Status: fixed | Handler: Alfred | Date: 2026-10-18

## PROBLEM
[Higiene workspace T-032] Barrido read-only de los 15 cerebros de proyecto (codec-cortex parse+validate): 497 errores en 12 de 15. ENVX_MCP 286 (263 E008 duplicados + 23 E032) | Manhattan 92 (45 E034 + 39 E032 + 8 E008) | Conquistadores 65 (55 E032 + 10 E034) | Banco Familiar 16 (14 E032 + 2 E008) | mi_club 15 (9 E033 entradas operativas en $0 + 6 E032) | ENVX_OPER 6 (5 E006 + 19 I001) | ARQUX 4 (E032) | Manhattan/BEX 4 (2 E006) | ENVX_EXEC 3 | ENVX_INFRA 3 | CODEC-CORTEX 2 | ENVX 1 | LOCAL/DEX/NEX 0. Las 6 identidades restantes (auditor/executor/governor/heimdall/jarvis/seshat) estan limpias. GAP: migrate_cortex_file (w11) se niega si el archivo valida y no completa campos requeridos vacios ('does NOT fabricate missing semantic fields'), asi que E032/E034 quedan sin ruta automatica; y E008 requiere cortex.gc por archivo. Esperado: una ruta de remediacion gobernada por proyecto (BLP) que distinga dedupe automatico (E008) de completado de campos (que exige criterio humano/evidencia, no fabricacion).

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T18:17:34Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

Triageado: paraguas de remediacion por proyecto (497 errores / 12 de 15 cerebros). Se resolvera con 1 BLP por proyecto.

## UPDATE 2026-10-23

Fixed parcial (T-044) — re-verificación 2026-10-23 y dedupe E008 gobernado aplicado vía cortex.gc (mode=dedupe, keep=first, con backup): ENVX_MCP 263 removidos (368→106 entries: E_0236×50, E_0286×~120, blueprints_done×12, sync_run×2, tasks_active×6), Banco Familiar 2 (AUD:event), CODEC-CORTEX 1 (sync_run), ENVX 1 (sync_run). E008 eliminado donde existía. Estado post-gc: CODEC-CORTEX y ENVX quedan valid=true; mi_club y ENVX_INFRA ya estaban limpios (remediados desde el barrido original); BEX sin brain.cortex. PENDIENTE por criterio humano (no fabricable): Conquistadores ~55×E032+~10×E034 (LNG sin prevention/cause), ENVX_MCP 23×E032+7×W002, Banco Familiar 14×E032+6×W002, ENVX_EXEC 1×E017+3×E032+6×W002, ENVX_OPER 20×I001+5×E006+1×W002, ARQUX 4×E034+1×I001, Manhattan 2×E034. Ruta: 1 BLP de remediación por proyecto con evidencia humana para completar campos — decisión del Arquitecto.
