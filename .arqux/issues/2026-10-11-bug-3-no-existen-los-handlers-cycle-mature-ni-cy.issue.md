# ISSUE: BUG-3: no existen los handlers cycle.mature ni cycle.gate en la superficie MCP (97 handlers). El workflow w12-cycle-lifecycle.md los exige en FASE 4 (cycle.mature lee §9 compuertas y transiciona draft->ready), y la identidad de Alfred (LNG:gates_antes_de_ready_0011, LNG:cycle_mature__) los da por disponibles. Consecuencia real observada en mi_club: los quality_gates del MANIFEST de CYCLE-02 quedaron en false tras 13 blueprints done, y CYCLE-03 queda en draft sin via de maduracion. Ademas blueprint.synthesize devuelve guide.next_section pero no expone los 6 quality gates. Impacto: los ciclos no pueden madurar via MCP.
# Severity: medium | Status: verified | Handler: alfred | Date: 2026-10-11

## PROBLEM
BUG-3: no existen los handlers cycle.mature ni cycle.gate en la superficie MCP (97 handlers). El workflow w12-cycle-lifecycle.md los exige en FASE 4 (cycle.mature lee §9 compuertas y transiciona draft->ready), y la identidad de Alfred (LNG:gates_antes_de_ready_0011, LNG:cycle_mature__) los da por disponibles. Consecuencia real observada en mi_club: los quality_gates del MANIFEST de CYCLE-02 quedaron en false tras 13 blueprints done, y CYCLE-03 queda en draft sin via de maduracion. Ademas blueprint.synthesize devuelve guide.next_section pero no expone los 6 quality gates. Impacto: los ciclos no pueden madurar via MCP.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T23:59:17Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Reencuadrado: no es un bug de handlers faltantes — cycle.mature fue ELIMINADO deliberadamente en BLP-003 (maquina de estados draft -> closed; 'la maduracion es conversacional, no un handler', ver docstring de handlers/cycle.py). El residual real es documental y sigue vivo: el workflow desplegado .arqux/skills/workflows/w12-cycle-lifecycle.md sigue exigiendo cycle.mature en FASE 4 (lineas 61, 94, 128, 141, 152-154) y las LNG de la identidad de Alfred lo dan por disponible. Fix correcto: actualizar w12 + lecciones de identidad al modelo conversacional (docs/arch_vision/w12 ya fue actualizado), o que el Arquitecto decida reintroducir compuertas. Ademas la observacion sobre quality_gates del MANIFEST quedo cubierta por el ciclo draft->closed.

## UPDATE 2026-10-16

Resuelto como deuda documental (los handlers no vuelven: eliminados por diseno en BLP-003). w12 reescrito al modelo real draft->closed con compuerta implicita de placeholders en blueprint.create; w13 desplegado sincronizado al del paquete; 7 lecciones de la identidad de Alfred que prescribian cycle.mature/blueprint.gate/blueprint.define marcadas superseded con puntero al modelo actual. w08 arch_vision y arqux-legacy-reference.skill.md quedan como referencia historica deliberada. Pendiente 'verified' por auditoria.
