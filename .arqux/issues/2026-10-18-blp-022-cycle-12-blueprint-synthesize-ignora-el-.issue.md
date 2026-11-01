# ISSUE: [BLP-022/CYCLE-12] blueprint.synthesize ignora el ciclo del contexto y resuelve/crea el bp_id en el ciclo MAS RECIENTE por orden, incluso si esta CERRADO. Reproducido en vivo: blueprint.create(cycle=CYCLE-12) escribio ARQUX/.arqux/cycles/CYCLE-12/blueprints/BLP-022.md (6251 B, title correcto), pero la llamada inmediata a blueprint.synthesize(bp_id=BLP-022) devolvio path=.../cycles/CYCLE-14/blueprints/BLP-022.md con created=true y title 'Synthesized', creando un BLP-022 vacio en CYCLE-14. Estado real de los ciclos: CYCLE-11 planned, CYCLE-12 current, CYCLE-13 done, CYCLE-14 closed. Es decir: synthesize escribio en un ciclo CERRADO, fuera del contexto de sesion (session.context_set fijo ARQUX/CYCLE-12). Consecuencias: (a) BLP duplicado y basura en un ciclo cerrado (archivado en .arqux/archive/hygiene-2026-10-18/BLP-022-spurious-CYCLE-14.md); (b) el flujo canonico de poblado (synthesize guide mode, exigido por las lecciones LNG:ante/bpl_synthesize_first) queda INUTILIZABLE para BLPs creados en un ciclo que no sea el mas reciente: no hay forma de fijar el ciclo porque synthesize no acepta el parametro cycle, mientras blueprint.update si lo acepta; (c) riesgo de contaminar ciclos cerrados con documentacion de diseno. Esperado: blueprint.synthesize debe aceptar cycle= y resolver por el ciclo activo/contexto, y rechazar crear en un ciclo cerrado. Relacionado: LNG:blueprint_synthesize_0001 y _0002 (mitigacion documentada: pasar cycle explicito en TODAS las llamadas posteriores).
# Severity: high | Status: verified | Handler: Alfred | Date: 2026-10-18

## PROBLEM
[BLP-022/CYCLE-12] blueprint.synthesize ignora el ciclo del contexto y resuelve/crea el bp_id en el ciclo MAS RECIENTE por orden, incluso si esta CERRADO. Reproducido en vivo: blueprint.create(cycle=CYCLE-12) escribio ARQUX/.arqux/cycles/CYCLE-12/blueprints/BLP-022.md (6251 B, title correcto), pero la llamada inmediata a blueprint.synthesize(bp_id=BLP-022) devolvio path=.../cycles/CYCLE-14/blueprints/BLP-022.md con created=true y title 'Synthesized', creando un BLP-022 vacio en CYCLE-14. Estado real de los ciclos: CYCLE-11 planned, CYCLE-12 current, CYCLE-13 done, CYCLE-14 closed. Es decir: synthesize escribio en un ciclo CERRADO, fuera del contexto de sesion (session.context_set fijo ARQUX/CYCLE-12). Consecuencias: (a) BLP duplicado y basura en un ciclo cerrado (archivado en .arqux/archive/hygiene-2026-10-18/BLP-022-spurious-CYCLE-14.md); (b) el flujo canonico de poblado (synthesize guide mode, exigido por las lecciones LNG:ante/bpl_synthesize_first) queda INUTILIZABLE para BLPs creados en un ciclo que no sea el mas reciente: no hay forma de fijar el ciclo porque synthesize no acepta el parametro cycle, mientras blueprint.update si lo acepta; (c) riesgo de contaminar ciclos cerrados con documentacion de diseno. Esperado: blueprint.synthesize debe aceptar cycle= y resolver por el ciclo activo/contexto, y rechazar crear en un ciclo cerrado. Relacionado: LNG:blueprint_synthesize_0001 y _0002 (mitigacion documentada: pasar cycle explicito en TODAS las llamadas posteriores).

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T18:23:51Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

Triageado: reproducible, bloquea el flujo canonico de poblado de BLPs fuera del ciclo mas reciente. Entra al mismo lote de bugs de handlers de CYCLE-12.

## UPDATE 2026-10-18

FIXED (pendiente verdicto del auditor): blueprint.synthesize acepta cycle=, resuelve por el ciclo de contexto y rechaza CYCLE_CLOSED sin crear archivo. Tests: test_synthesize_never_writes_to_a_closed_cycle, test_synthesize_refuses_a_closed_cycle_without_creating_a_file. Evidencia E-1842.

## UPDATE 2026-10-18

Verified por verdicto E-1858 (heimdall): blueprint.synthesize acepta cycle=, resuelve por el ciclo de contexto y rechaza CYCLE_CLOSED sin crear archivo. Tests test_synthesize_never_writes_to_a_closed_cycle / test_synthesize_refuses_a_closed_cycle_without_creating_a_file.
