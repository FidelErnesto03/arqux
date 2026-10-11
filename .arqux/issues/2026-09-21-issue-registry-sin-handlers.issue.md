# ISSUE: Registro de issues sin handler MCP gobernado
# Severity: low | Status: verified | Handler: heimdall (hallazgo HD-09, documentado por alfred) | Date: 2026-09-21

## PROBLEM
Las mutaciones del registro `.arqux/issues/` (crear issue, cambiar status,
triaje) se realizan por edicion directa de archivos. No existe handler
`issue.*` en el servidor MCP, por lo que estas mutaciones de gobernanza
carecen de via sancionada, validacion y trazabilidad PULSE.

## WHAT_HAPPENING
Triaje formal del registro (normalizacion de `status` segun la convencion
de la skill arqux-issues) durante la sesion 2026-09-21. Todos los cambios
de estado se aplicaron con edicion nativa de archivos .md/.cortex.

## EXPECTED
Un handler `issue.*` (create/update/list/read) que escriba las mutaciones
con validacion y registro en PULSE, igual que task.*/blueprint.*.

## ACTUAL
Solo `cortex.*` cubre archivos .cortex; los .md de issues quedan fuera del
alcance de cualquier handler. La skill arqux-issues documenta `cat`/`ls`
como flujo, estableciendo el precedente de acceso nativo.

## CONTEXT
files: .arqux/issues/*.md, .arqux/skills/arqux-issues.skill.md
related: BLP-003 (gap equivalente para frontmatter de MANIFEST/BLPs)

## LESSON
cause:   El registry de issues crecio como archivos planos sin handler
         dedicado; cortex.* no cubre .md y no modela el ciclo de vida
         de un issue (status, severidad, escalado a BLP).
fix:     Implementar issue.create/issue.update/issue.list/issue.read
         con escritura validada y evento PULSE por mutacion.
prevention: Toda nueva superficie de gobernanza mutable debe nacer con
         handler MCP; la edicion directa queda reservada a excepciones
         autorizadas por el Arquitecto.

## UPDATE 2026-09-30

Handlers issue.create/update/list/read implementados y certificados (T-027 CYCLE-12): mutaciones con validacion y evento PULSE por transicion; status=verified exige audit_ref del auditor. Skill arqux-issues actualizada al flujo gobernado.

## UPDATE 2026-10-01

Cierre documental (auditoría de implementación real 2026-10-01). Verificado en código: issue.py:351-419 expone issue.create/update/list/read; MUTATING_HANDLERS incluye create/update; transición a verified exige audit_ref. Auditoría sustantiva: T-027 'AUDITORÍA HEIMDALL: APPROVED (round 1)'. audit_ref=E-0997.
