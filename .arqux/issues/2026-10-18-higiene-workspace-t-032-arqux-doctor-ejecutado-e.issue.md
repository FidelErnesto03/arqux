# ISSUE: [Higiene workspace T-032] `arqux doctor` ejecutado en el workspace root exige un directorio `cycles` y reporta WARN 'Missing: cycles', lo que contradice AXM:no_workspace_project (el workspace root es contenedor: NO cycles, NO blueprints). Ademas existen DOS superficies de diagnostico que reportan distinto sobre el mismo arbol: `arqux doctor` (4 checks) y workspace_status(dashboard=true) (8 checks: nested .arqux, orphan dirs, residue files, metadata-section, meta-brain, .bak en git). El FAIL de 'nested .arqux' solo aparecia en la segunda. Impacto: un agente que confie solo en `arqux doctor` cree el arbol sano cuando no lo esta; y el WARN de cycles induce a crear un directorio prohibido por la axiom. Esperado: el doctor del workspace no exija `cycles` y ambas superficies compartan el mismo conjunto de checks.
# Severity: medium | Status: fixed | Handler: Alfred | Date: 2026-10-18

## PROBLEM
[Higiene workspace T-032] `arqux doctor` ejecutado en el workspace root exige un directorio `cycles` y reporta WARN 'Missing: cycles', lo que contradice AXM:no_workspace_project (el workspace root es contenedor: NO cycles, NO blueprints). Ademas existen DOS superficies de diagnostico que reportan distinto sobre el mismo arbol: `arqux doctor` (4 checks) y workspace_status(dashboard=true) (8 checks: nested .arqux, orphan dirs, residue files, metadata-section, meta-brain, .bak en git). El FAIL de 'nested .arqux' solo aparecia en la segunda. Impacto: un agente que confie solo en `arqux doctor` cree el arbol sano cuando no lo esta; y el WARN de cycles induce a crear un directorio prohibido por la axiom. Esperado: el doctor del workspace no exija `cycles` y ambas superficies compartan el mismo conjunto de checks.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T18:16:51Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

Triageado: falso positivo del doctor (exige cycles en el workspace root, contra AXM:no_workspace_project) + divergencia entre las dos superficies de diagnostico.

## UPDATE 2026-10-23

Fixed (T-041) — verificado con evidencia: el falso positivo ya no se reproduce. `arqux doctor` en workspace root devuelve 7 checks context-aware (structure check espera [identities,skills,templates,packages] en workspace, [cycles,packages] solo en proyecto — commit 3ef422f del 2026-10-16, previo al reporte; el MCP server observado corría versión anterior). Divergencia eliminada: workspace_status(dashboard) renderiza la salida del propio doctor via dashboard._parse_health_checks — una sola fuente de checks. Los hallazgos actuales SÍ son reales (no falsos positivos del doctor): /home/vatrox/workspace/.arqux/.arqux/ es un dir duplicado con brain.cortex.lock residual (FAIL nested, WARN orphan) y hay residue .lock/.bak — limpieza física queda pendiente de autorización del Arquitecto (borrado en governance dir).
