# ISSUE: Drift test-vs-skill en tests/test_c14_blp005_skill_matrix.py: TestAc06DiscoveryHonesty::test_projection_is_marked_pending espera 'PENDIENTE' y 'BLP-006' y TestAc07NoExternalEffects::test_matrix_states_external_is_optional_and_inactive espera 'no se activa en esta fase' en src/arqux/skills/protocol.skill.md; el skill evoluciono a 'puente opcional que se activa solo por instruccion del Arquitecto via timelog.project' y ya no contiene esas cadenas. Resultado: 2 fallos preexistentes en la suite base (no atribuibles a BLP-022). Detectado al verificar la precondicion §3.1 de BLP-022 (baseline no verde). Fuera del alcance de BLP-022 (§7.8/§16.4): registrar, no ampliar.
# Severity: medium | Status: verified | Handler: Alfred | Date: 2026-10-18

## PROBLEM
Drift test-vs-skill en tests/test_c14_blp005_skill_matrix.py: TestAc06DiscoveryHonesty::test_projection_is_marked_pending espera 'PENDIENTE' y 'BLP-006' y TestAc07NoExternalEffects::test_matrix_states_external_is_optional_and_inactive espera 'no se activa en esta fase' en src/arqux/skills/protocol.skill.md; el skill evoluciono a 'puente opcional que se activa solo por instruccion del Arquitecto via timelog.project' y ya no contiene esas cadenas. Resultado: 2 fallos preexistentes en la suite base (no atribuibles a BLP-022). Detectado al verificar la precondicion §3.1 de BLP-022 (baseline no verde). Fuera del alcance de BLP-022 (§7.8/§16.4): registrar, no ampliar.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T18:46:12Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

FIXED (T-036): aserciones alineadas con protocol.skill.md vigente (proyeccion implementada via timelog.project; externo 'puente opcional ... solo por instruccion del Arquitecto'). tests/test_c14_blp005_skill_matrix.py 20 passed; suite 2414 passed / 0 failed.

## UPDATE 2026-10-22

VEREDICTO AUDITOR (Heimdall, read-only) 2026-10-22: CONFORME. tests/test_c14_blp005_skill_matrix.py pasa en verde: las aserciones quedaron alineadas con el protocol.skill.md vigente (proyeccion via timelog.project; externo como puente opcional activado solo por instruccion del Arquitecto). El drift test-vs-skill ya no existe. Sin hallazgos. Se marca verified.

## UPDATE 2026-10-22

Verificado por verificacion del auditor Heimdall (ref E-1922). Cerrado.
