# ISSUE: Contradicción documental en protocol.skill.md (desplegada = fuente, 13937 B, 2026-10-15): §7 mantiene STP:timelog_gate del modelo viejo (skill timelog-compliance + watermark KNW:timelog_watermark_* + tw_log como mecanismo de cierre), mientras §8 (CYCLE-14) declara el modelo nativo con AXM:timelog_no_dedicated_calls ('NO arranca cronómetros', límites naturales vía lifecycle handlers). Además HDL:timelog.project figura como 'PENDIENTE — BLP-006' pero el handler ya está implementado y registrado en MCP (timelog_project con acciones preview/prepare/send/reconcile, handlers/timelog.py). Acciones: (a) reconciliar §7 con §8 — el gate viejo debe referenciar el modelo nativo o retirarse; (b) actualizar estado de timelog.project en el skill; (c) evaluar si timelog-compliance.skill.md v2.2.1 debe aclarar que es puente externo opcional y no el mecanismo de registro.
# Severity: medium | Status: verified | Handler: alfred | Date: 2026-10-16

## PROBLEM
Contradicción documental en protocol.skill.md (desplegada = fuente, 13937 B, 2026-10-15): §7 mantiene STP:timelog_gate del modelo viejo (skill timelog-compliance + watermark KNW:timelog_watermark_* + tw_log como mecanismo de cierre), mientras §8 (CYCLE-14) declara el modelo nativo con AXM:timelog_no_dedicated_calls ('NO arranca cronómetros', límites naturales vía lifecycle handlers). Además HDL:timelog.project figura como 'PENDIENTE — BLP-006' pero el handler ya está implementado y registrado en MCP (timelog_project con acciones preview/prepare/send/reconcile, handlers/timelog.py). Acciones: (a) reconciliar §7 con §8 — el gate viejo debe referenciar el modelo nativo o retirarse; (b) actualizar estado de timelog.project en el skill; (c) evaluar si timelog-compliance.skill.md v2.2.1 debe aclarar que es puente externo opcional y no el mecanismo de registro.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-16T14:19:08Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Verificado sobre la skill desplegada (/home/vatrox/workspace/.arqux/skills/protocol.skill.md): la contradiccion sigue viva — linea 115 mantiene STP:timelog_gate del modelo viejo (skill + watermark + tw_log) y la linea 141 sigue marcando HDL:timelog.project como 'PENDIENTE — BLP-006', mientras el handler ya esta implementado y registrado (timelog_project, acciones preview/prepare/send/reconcile en handlers/timelog.py). Las tres acciones propuestas (a/b/c) siguen pendientes.
