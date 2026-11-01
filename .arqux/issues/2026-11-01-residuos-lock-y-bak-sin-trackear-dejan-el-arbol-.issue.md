# ISSUE: Residuos .lock y .bak sin trackear dejan el arbol sucio y health WARN
# Severity: low | Status: verified | Handler: Alfred (hallazgo en CODEC-CORTEX, sesiones SES001/SES002) | Date: 2026-11-01

## PROBLEM
## Sintoma
Cada sesion deja archivos `.lock` y `.bak` sin trackear en `.arqux/`. El arbol queda sucio despues de cada cierre y el health del workspace reporta `residue files WARN` de forma permanente.

## Evidencia (CODEC-CORTEX, 2026-11-01)
- Tras cada cierre: `.arqux/.sessions.lock`, `.arqux/brain.cortex.lock`, `.arqux/brain.cortex.bak.1` sin trackear.
- `workspace_status` devuelve `residue files | WARN` de forma recurrente.
- En el cierre de SES001 y SES002 el `git status` quedo con 3-4 entradas de residuo; hubo que decidir manualmente que no commitear.

## Reproduccion
1. Abrir y cerrar una sesion.
2. `git status --short` en el proyecto: aparecen `.sessions.lock`, `brain.cortex.lock` y `.bak.1`.
3. `workspace_status`: health WARN por residuos.

## Esperado
- Los `.lock` se limpian al cerrar o se declaran en `.gitignore` generado por ArqUX.
- Los `.bak`/`.bak.N` tienen politica explicita (retencion, rotacion, ignorados).
- El health distingue residuo esperado de residuo anomalo.

## Actual
- Los archivos quedan, no estan ignorados y el health los cuenta como warning sin accion posible.

## Impacto
Ruido en cada cierre, riesgo de commitear basura, fatiga de warnings y perdida de senal del health (un WARN permanente deja de mirarse).

## Propuesta
- `.gitignore` gestionado por `workspace.init`/`project.init` con patrones de lock y bak.
- Limpieza de locks en `session.close` (con manejo de locks huerfanos por PID).
- Politica de backups: mantener `.bak` y `.bak.1`, rotar, documentar.
- Health: `residue files` PASS si solo hay locks/baks esperados.

## Criterios de aceptacion
- AC-1: tras `session.close`, el arbol no muestra locks sin trackear.
- AC-2: `.bak*` esta ignorado o documentado.
- AC-3: `workspace_status` no reporta WARN por residuo esperado.

## CONTEXT
reported_by: Alfred
reported_at: 2026-11-01T20:10:21Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-11-01

Heimdall SIGNED-PASS audit 2.0: fixable .gitignore residue check in doctor, applied to ARQUX+CODEC-CORTEX (168ea65, 92b2ad4)
