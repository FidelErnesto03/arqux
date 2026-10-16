# ISSUE: blueprint.claim resuelve el agente ejecutor desde el agente autenticado del servidor MCP (PermissionContext.from_env), ignorando la identidad activa del contexto (session.context/identity.switch). Efecto: tras identity.switch a jarvis, blueprint.claim registró executor=alfred en BLP-014 (Conquistadores, CYCLE-04). No existe handler expuesto para fijar/cambiar el ejecutor (no hay blueprint.assign; blueprint.frontmatter.update solo acepta title/cycle). Recomendación: (a) que claim lea el agente activo del contexto, o acepte un parámetro agent_id; (b) exponer blueprint.assign o extender frontmatter.update para declarar executor antes del claim; (c) permitir transición in_progress→ready para reclamar limpio. Detectado durante handoff Alfred→Jarvis.
# Severity: medium | Status: verified | Handler: alfred | Date: 2026-10-02

## PROBLEM
blueprint.claim resuelve el agente ejecutor desde el agente autenticado del servidor MCP (PermissionContext.from_env), ignorando la identidad activa del contexto (session.context/identity.switch). Efecto: tras identity.switch a jarvis, blueprint.claim registró executor=alfred en BLP-014 (Conquistadores, CYCLE-04). No existe handler expuesto para fijar/cambiar el ejecutor (no hay blueprint.assign; blueprint.frontmatter.update solo acepta title/cycle). Recomendación: (a) que claim lea el agente activo del contexto, o acepte un parámetro agent_id; (b) exponer blueprint.assign o extender frontmatter.update para declarar executor antes del claim; (c) permitir transición in_progress→ready para reclamar limpio. Detectado durante handoff Alfred→Jarvis.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-02T22:38:49Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-02

FIX implementado en src/arqux/handlers/blueprint/lifecycle.py (claim_blueprint) + schema MCP actualizado (blueprint.claim ahora expone agent_id). CAUSE: claim resolvia el ejecutor unicamente desde PermissionContext.from_env() (agente autenticado estatico del server MCP), ignorando el puntero de contexto activo que identity.switch/session.context.set escriben en .arqux/context.cortex. FIX — precedencia de resolucion del ejecutor: (1) parametro agent_id explicito (solo role governor; si no, PERMISSION_DENIED), (2) executor declarado en frontmatter + caller governor (preexistente), (3) agente activo del context.cortex via composicion context_get (nuevo helper _active_context_agent), (4) agente autenticado del env (fallback legacy). Se cubrio ademas la recomendacion (b) parcial del issue: el agent_id explicito da via de asignacion/correccion sin necesidad de blueprint.assign. Recomendacion (c) (transicion in_progress→ready) no implementada: considerada innecesaria con la via (1)/(3). TESTS: nuevo tests/test_claim_executor_resolution.py con 7 casos (contexto activo gana sobre env, agent_id governor-only, env fallback sin contexto, executor declarado respetado y prevalece sobre contexto divergente, denegacion para executor). Suite ARQUX: 1851 passed, 14 skipped. PREVENTION: cualquier handler que registre un actor debe leer el puntero de contexto activo (context.cortex) como fuente de identidad operativa, y derivar el agente del env solo como fallback. NOTA: efecto observable en server MCP tras respawn; el executor erroneo en BLP-014 (Conquistadores) queda pendiente de correccion con claim por agent_id o frontmatter.update si se requiere.
