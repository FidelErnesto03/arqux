# ISSUE: El hook de pre-commit `surface-homologation` (scripts/check_surfaces.py) reporta un FALSO FALLO "brain ARQX:artifact version: expected 0.9.0rc1, found none" cuando `.arqux/brain.cortex` está modificado pero UNSTAGED. Causa: `.arqux/brain.cortex` está TRACKED (134 archivos .arqux ya versionados; `.git/info/exclude` no destrackea lo ya versionado) y pre-commit stashea los cambios unstaged antes de correr los hooks, de modo que el check lee la versión de HEAD (que no tiene el campo version). Impacto: bloquea commits legítimos con un mensaje engañoso — parece divergencia de superficies cuando no la hay. Evidencia: commit c5db415 — el hook falló 2 veces con el brain unstaged y pasó al stagarlo (`git add .arqux/brain.cortex`). Fix propuesto: (a) que el script detecte el patrón "archivo tracked + modificación unstaged" y lo advierta con precisión; (b) que el check lea explícitamente del índice o del working tree; o (c) documentar que los cambios del brain.cortex deben ir staged en el mismo commit. Workaround actual: stagear `.arqux/brain.cortex` antes de commitear.
# Severity: medium | Status: verified | Handler: scripts/check_surfaces.py | Date: 2026-10-10

## PROBLEM
El hook de pre-commit `surface-homologation` (scripts/check_surfaces.py) reporta un FALSO FALLO "brain ARQX:artifact version: expected 0.9.0rc1, found none" cuando `.arqux/brain.cortex` está modificado pero UNSTAGED. Causa: `.arqux/brain.cortex` está TRACKED (134 archivos .arqux ya versionados; `.git/info/exclude` no destrackea lo ya versionado) y pre-commit stashea los cambios unstaged antes de correr los hooks, de modo que el check lee la versión de HEAD (que no tiene el campo version). Impacto: bloquea commits legítimos con un mensaje engañoso — parece divergencia de superficies cuando no la hay. Evidencia: commit c5db415 — el hook falló 2 veces con el brain unstaged y pasó al stagarlo (`git add .arqux/brain.cortex`). Fix propuesto: (a) que el script detecte el patrón "archivo tracked + modificación unstaged" y lo advierta con precisión; (b) que el check lea explícitamente del índice o del working tree; o (c) documentar que los cambios del brain.cortex deben ir staged en el mismo commit. Workaround actual: stagear `.arqux/brain.cortex` antes de commitear.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T01:45:32Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Confirmado en codigo (SES005): scripts/check_surfaces.py sigue leyendo el working tree via _scan y no detecta el patron 'archivo tracked + modificacion unstaged'; .pre-commit-config.yaml sin cambios (always_run, pass_filenames:false). Los commits posteriores al reporte (b940f9c, 8c4acf5) tocaron otras superficies, no esta causa. El falso fallo sigue reproducible: pre-commit stashea lo unstaged y el check lee HEAD sin el campo version. Workaround vigente: stagear .arqux/brain.cortex antes de commitear.

## UPDATE 2026-10-16

Corregido con la opcion (a) del issue: el check detecta el patron 'archivo tracked + modificacion unstaged' via git diff --name-only y reporta con precision que pre-commit stasheo el cambio y hay que stagear el archivo, en vez del falso fallo de superficie. El bloqueo del commit se mantiene (correcto: hay que stagear el fix); lo que cambia es el diagnostico. Pendiente verified por auditoria.
