# ISSUE: El hook de pre-commit `surface-homologation` (scripts/check_surfaces.py) reporta un FALSO FALLO "brain ARQX:artifact version: expected 0.9.0rc1, found none" cuando `.arqux/brain.cortex` está modificado pero UNSTAGED. Causa: `.arqux/brain.cortex` está TRACKED (134 archivos .arqux ya versionados; `.git/info/exclude` no destrackea lo ya versionado) y pre-commit stashea los cambios unstaged antes de correr los hooks, de modo que el check lee la versión de HEAD (que no tiene el campo version). Impacto: bloquea commits legítimos con un mensaje engañoso — parece divergencia de superficies cuando no la hay. Evidencia: commit c5db415 — el hook falló 2 veces con el brain unstaged y pasó al stagarlo (`git add .arqux/brain.cortex`). Fix propuesto: (a) que el script detecte el patrón "archivo tracked + modificación unstaged" y lo advierta con precisión; (b) que el check lea explícitamente del índice o del working tree; o (c) documentar que los cambios del brain.cortex deben ir staged en el mismo commit. Workaround actual: stagear `.arqux/brain.cortex` antes de commitear.
# Severity: medium | Status: open | Handler: scripts/check_surfaces.py | Date: 2026-10-10

## PROBLEM
El hook de pre-commit `surface-homologation` (scripts/check_surfaces.py) reporta un FALSO FALLO "brain ARQX:artifact version: expected 0.9.0rc1, found none" cuando `.arqux/brain.cortex` está modificado pero UNSTAGED. Causa: `.arqux/brain.cortex` está TRACKED (134 archivos .arqux ya versionados; `.git/info/exclude` no destrackea lo ya versionado) y pre-commit stashea los cambios unstaged antes de correr los hooks, de modo que el check lee la versión de HEAD (que no tiene el campo version). Impacto: bloquea commits legítimos con un mensaje engañoso — parece divergencia de superficies cuando no la hay. Evidencia: commit c5db415 — el hook falló 2 veces con el brain unstaged y pasó al stagarlo (`git add .arqux/brain.cortex`). Fix propuesto: (a) que el script detecte el patrón "archivo tracked + modificación unstaged" y lo advierta con precisión; (b) que el check lea explícitamente del índice o del working tree; o (c) documentar que los cambios del brain.cortex deben ir staged en el mismo commit. Workaround actual: stagear `.arqux/brain.cortex` antes de commitear.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T01:45:32Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
