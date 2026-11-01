# ISSUE: [Higiene workspace T-032] task.claim ejecutado SIN sesion vinculada devuelve 'lifecycle=status:skipped;coverage:limited;reason:no session bound to this execution' y la advertencia TIMELOG_UNBOUND ('task.claim wrote no native timelog block... This work is NOT registered'). Es decir: el trabajo se marca in_progress pero NO queda registrado en el timelog nativo. El claim no fuerza ni sugiere vincular sesion, asi que es facil ejecutar trabajo no registrado sin notarlo. Evidencia: E-1797 (claim de T-032) vs SES006 abierta despues con session.context_set. Es el mismo patron del issue 2026-10-16-session-close-sin-sesion-bound (cierre de sesion sin sesion vinculada) y del timelog vacio observado en el workspace. Esperado: (a) task.claim deberia fallar o exigir session.context_set cuando no hay sesion vinculada, y (b) session.close deberia negarse si la sesion no esta vinculada, en vez de dejar el trabajo sin registrar.
# Severity: high | Status: verified | Handler: Alfred | Date: 2026-10-18

## PROBLEM
[Higiene workspace T-032] task.claim ejecutado SIN sesion vinculada devuelve 'lifecycle=status:skipped;coverage:limited;reason:no session bound to this execution' y la advertencia TIMELOG_UNBOUND ('task.claim wrote no native timelog block... This work is NOT registered'). Es decir: el trabajo se marca in_progress pero NO queda registrado en el timelog nativo. El claim no fuerza ni sugiere vincular sesion, asi que es facil ejecutar trabajo no registrado sin notarlo. Evidencia: E-1797 (claim de T-032) vs SES006 abierta despues con session.context_set. Es el mismo patron del issue 2026-10-16-session-close-sin-sesion-bound (cierre de sesion sin sesion vinculada) y del timelog vacio observado en el workspace. Esperado: (a) task.claim deberia fallar o exigir session.context_set cuando no hay sesion vinculada, y (b) session.close deberia negarse si la sesion no esta vinculada, en vez de dejar el trabajo sin registrar.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T18:17:24Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

Triageado: bug de handler que produce registro silenciosamente incompleto. Va a BLP prioritario (ciclo de bug fixes de handlers).

## UPDATE 2026-10-18

FIXED (pendiente verdicto del auditor para verified): task.claim/complete y blueprint.claim/complete rechazan SESSION_UNBOUND ANTES de mutar cuando el proyecto tiene identidad de sesion y ninguna esta vinculada; session.close ya lo exigia (H-01). Sin sesiones (legacy/CI) procede con aviso TIMELOG_UNBOUND. Tests: test_unbound_writers_reject_when_session_identity_exists, test_close_unbound_rejects. Evidencia E-1833..E-1836.

## UPDATE 2026-10-18

Verified por verdicto E-1858 (heimdall): task.claim/complete y blueprint.claim/complete rechazan SESSION_UNBOUND antes de mutar; session.close ya lo exigia. Tests test_unbound_writers_reject_when_session_identity_exists / test_close_unbound_rejects; V-07 10/10.
