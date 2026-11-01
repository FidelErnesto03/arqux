# ISSUE: El puntero global de contexto hizo que un checkpoint escribiera en el brain equivocado
# Severity: high | Status: fixed | Handler: Alfred | Date: 2026-10-28

## PROBLEM
cortex.checkpoint sin path resolvio el proyecto por la ranura global .arqux/context.cortex, que otro cliente habia reescrito. Escribio el estado de trabajo de ARQUX en el brain de Manhattan. La working memory de Manhattan quedo corrupta y su contenido original no es recuperable.

Reproduccion: dos clientes con proyectos distintos; el segundo reescribe context.cortex; el primero llama checkpoint sin path.

Corregido en 1b679a7: el resolvedor lee primero .arqux/contexts/<exec>.cortex.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-28T19:49:25Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-28

Corregido en 1b679a7 (rama feat/governance-integrity-2026-10-28, PR #1). find_project_root y checkpoint._resolve_active_root leen primero .arqux/contexts/<exec>.cortex; la ranura global queda como respaldo. El brain de Manhattan se reparo con un estado honesto: su working memory original no es recuperable y ahora lo declara. Tests: tests/test_t046_context_pointer_precedence.py (3 casos). Suite 2548 passed.
