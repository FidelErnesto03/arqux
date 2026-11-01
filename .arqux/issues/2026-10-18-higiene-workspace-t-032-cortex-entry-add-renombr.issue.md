# ISSUE: [Higiene workspace T-032] cortex.entry.add renombra silenciosamente la clave cuando hay colision de nombre, y eso dejo los dos registries de proyectos del workspace desincronizados en sus CLAVES (mismo proyecto, distinta clave): projects.cortex usa manhattan_0001, mi_club_0001, bex_0002, nex_0003, dex_0004; meta-brain usa manhattan, mi_club, BEX, NEX, DEX. Tambien aparecio AXM:no_workspace_project_0002 (sufijo _0002) sin que existiera una entrada AXM:no_workspace_project canonica en el archivo destino, y DOM:envx_mcp_0001. Evidencia: .arqux/projects.cortex y .arqux/meta-brain.cortex (verificados valid=true tras la higiene). Impacto: las herramientas que reconcilian por clave (no por atributo name) ven proyectos distintos en cada registro; los wildcards no resuelven. Esperado: (a) avisar o fallar en vez de renombrar silenciosamente, o (b) exponer un mapeo nombre->clave canonico, o (c) que la reconciliacion de registries compare por el atributo name.
# Severity: medium | Status: fixed | Handler: Alfred | Date: 2026-10-18

## PROBLEM
[Higiene workspace T-032] cortex.entry.add renombra silenciosamente la clave cuando hay colision de nombre, y eso dejo los dos registries de proyectos del workspace desincronizados en sus CLAVES (mismo proyecto, distinta clave): projects.cortex usa manhattan_0001, mi_club_0001, bex_0002, nex_0003, dex_0004; meta-brain usa manhattan, mi_club, BEX, NEX, DEX. Tambien aparecio AXM:no_workspace_project_0002 (sufijo _0002) sin que existiera una entrada AXM:no_workspace_project canonica en el archivo destino, y DOM:envx_mcp_0001. Evidencia: .arqux/projects.cortex y .arqux/meta-brain.cortex (verificados valid=true tras la higiene). Impacto: las herramientas que reconcilian por clave (no por atributo name) ven proyectos distintos en cada registro; los wildcards no resuelven. Esperado: (a) avisar o fallar en vez de renombrar silenciosamente, o (b) exponer un mapeo nombre->clave canonico, o (c) que la reconciliacion de registries compare por el atributo name.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T18:17:03Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

Triageado: cambio de contrato de entry.add (colision de claves). Requiere decision de diseno: fallar/avisar vs reconciliar por name.

## UPDATE 2026-10-23

Fixed (T-042) — opción (a) ya estaba implementada vía BLP-007 (renamed/requested explícitos en OUT-WORK); el bug real residual era el numerador: _next_number usaba un contador por-proceso, produciendo sufijos ajenos al archivo (AXM:no_workspace_project_0002 sin _0001 canónico) y no determinista entre reinicios. Reescrito: el sufijo se deriva del contenido del archivo (max {base}_NNNN + 1 por base+sigil+sección) — cada base numera independiente y consistente. Regresión test_entry_add_suffix_derives_from_file_not_process. PENDIENTE (datos, no código): los registries ya desincronizados (projects.cortex manhattan_0001 vs meta-brain manhattan) requieren reconciliación por name — decisión del Arquitecto, no automática.
