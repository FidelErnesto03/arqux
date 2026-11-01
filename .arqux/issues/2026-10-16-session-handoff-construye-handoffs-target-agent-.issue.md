# ISSUE: session.handoff construye handoffs/<target_agent>.cortex y el campo to: del HOF con el valor verbatim. Un llamado con payload multilinea (target_agent='heimdall\nsummary:...\nblps:\ntasks:') genero 2 archivos de nombre corrupto en .arqux/handoffs del workspace (2026-07-18). El mismo patron sin validar existia en identity_resolver/_unified/_helpers donde un parametro llega a f'{x}.cortex'.
# Severity: medium | Status: verified | Handler: Alfred | Date: 2026-10-16

## PROBLEM
session.handoff construye handoffs/<target_agent>.cortex y el campo to: del HOF con el valor verbatim. Un llamado con payload multilinea (target_agent='heimdall\nsummary:...\nblps:\ntasks:') genero 2 archivos de nombre corrupto en .arqux/handoffs del workspace (2026-07-18). El mismo patron sin validar existia en identity_resolver/_unified/_helpers donde un parametro llega a f'{x}.cortex'.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-16T16:22:16Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Fix: NAME_COMPONENT_RE + is_name_component() en constants.py; guarda aplicada en session.handoff (INVALID_ARGS antes de tocar filesystem), identity_resolver, learning/_unified y blueprint/_helpers. Tests nuevos: rechazo de multilinea/traversal/separador/espacio + slug canonico aceptado. En vivo: handoff('heimdall\nsummary:...') -> INVALID_ARGS.

## UPDATE 2026-10-22

VEREDICTO AUDITOR (Heimdall, read-only) 2026-10-22: CONFORME. is_name_component() (constants.py:132) se aplica antes de tocar el filesystem en session.handoff (handlers/session.py:1235), identity_resolver.py:40, core/learning/_unified.py:51 y handlers/blueprint/_helpers.py:485; payloads multilinea/separadores/traversal devuelven INVALID_ARGS. Tests de rechazo y slug canonico presentes. Sin hallazgos. Se marca verified.

## UPDATE 2026-10-22

Verificado por verificacion del auditor Heimdall (ref E-1921). Cerrado.
