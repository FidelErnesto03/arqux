# ISSUE: identity.switch exige path explicito aunque exista contexto de sesion activo
# Severity: medium | Status: verified | Handler: Alfred (hallazgo en CODEC-CORTEX, sesiones SES001/SES002) | Date: 2026-11-01

## PROBLEM
## Sintoma
`identity.switch(agent_id="heimdall")` falla con `NOT_FOUND no project initialized` aunque existe una sesion y un contexto de proyecto activos. Con `path` explicito funciona. El error no dice que falta el path.

## Evidencia (CODEC-CORTEX, 2026-11-01)
- Llamada `identity_switch(agent_id=heimdall)` -> `OUT-ERROR code=NOT_FOUND no project initialized`.
- Misma llamada con `path=/home/vatrox/workspace/CODEC-CORTEX` -> `identity.switch ok`, header y handoff correctos.
- El contexto activo era SES001 (CYCLE-03/BLP-006), con brain y sesion abiertos.

## Reproduccion
1. Abrir una sesion en un proyecto (`session.context.set`).
2. `identity.switch(agent_id=otro)` sin `path`.
3. Resultado: NOT_FOUND generico.

## Esperado
- Resolver el path desde el contexto de sesion activo (`.arqux/contexts/<exec>.cortex`) igual que otros handlers.
- Si no hay contexto, error `PROJECT_REQUIRED` que nombre el parametro faltante y las alternativas.

## Actual
- El handler no usa el contexto activo y devuelve un NOT_FOUND ambiguo.

## Impacto
El handoff de identidad se bloquea o exige un path redundante; en automatizaciones multiagente el error se interpreta como "proyecto inexistente" y se reintenta mal.

## Propuesta
- Reusar el resolvedor de contexto de `cortex.checkpoint`/`session.context` (precedencia `.arqux/contexts/<exec>.cortex`).
- Mensaje `PROJECT_REQUIRED: pass path= or set an active session context`.
- Test con y sin contexto activo.

## Criterios de aceptacion
- AC-1: con sesion activa, `identity.switch` sin path funciona y registra el handoff.
- AC-2: sin contexto, el error nombra `path` y no dice NOT_FOUND.
- AC-3: test de ambos caminos.

## CONTEXT
reported_by: Alfred
reported_at: 2026-11-01T20:10:01Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-11-01

Heimdall SIGNED-PASS audit 2.0: per-execution context pointer resolution before cwd (168ea65)
