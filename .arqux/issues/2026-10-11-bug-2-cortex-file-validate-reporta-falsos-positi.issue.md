# ISSUE: BUG-2: cortex_file_validate reporta falsos positivos de duplicados. En mi_club/.arqux/brain.cortex senalo 87 duplicados en la seccion $6 PULSE, cuando grep verifica 88 entradas AUD con 88 nombres unicos y 0 duplicados reales. Ejecutar fix=true renombraria los 87 eventos de evidencia (E_0110..E_0249) y destruiria el historial. Impacto: cualquier agente que siga el hint del handler con fix=true corrompe la evidencia de forma irreversible. Recomendacion: revisar el criterio de comparacion de nombres antes de promover fix=true, y documentar el riesgo en la skill.
# Severity: high | Status: verified | Handler: alfred | Date: 2026-10-11

## PROBLEM
BUG-2: cortex_file_validate reporta falsos positivos de duplicados. En mi_club/.arqux/brain.cortex senalo 87 duplicados en la seccion $6 PULSE, cuando grep verifica 88 entradas AUD con 88 nombres unicos y 0 duplicados reales. Ejecutar fix=true renombraria los 87 eventos de evidencia (E_0110..E_0249) y destruiria el historial. Impacto: cualquier agente que siga el hint del handler con fix=true corrompe la evidencia de forma irreversible. Recomendacion: revisar el criterio de comparacion de nombres antes de promover fix=true, y documentar el riesgo en la skill.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T23:59:16Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Corregido (BLP-046/BUG-002, commit 269d92c): _group_key solo colapsa una variante con sufijo _NNNN sobre su base cuando el nombre base existe verbatim en la misma (seccion,sigil) — la convencion AUD:E_NNNN de PULSE ya no colisiona. fix=true renombra por referencia directa al nodo (no por busqueda de nombre con break), asi que converge. Ademas escribe con strict=False, sin re-inyectar el dialecto rc1. tests/test_file_validate.py + tests/test_dialect_false_positives.py: 15 tests en verde. Pendiente 'verified' a cargo del auditor (Heimdall) con audit_ref.
