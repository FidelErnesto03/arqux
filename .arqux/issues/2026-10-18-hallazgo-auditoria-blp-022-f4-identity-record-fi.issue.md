# ISSUE: [Hallazgo auditoria BLP-022 / F4] identity.record: filed_in_brain se marca True inmediatamente despues de crud_add al brain, sin inspeccionar el dict devuelto; una escritura al brain que retorne {'error': ...} se reporta como filed y el handler devuelve OUT-WORK con destination=brain aunque nada se haya persistido. Esperado: comprobar 'error' en el resultado de crud_add antes de marcar filed_in_brain (y degradar a DESTINATION_NOT_ALLOWED si falla y el contrato tambien rechaza).
# Severity: low | Status: verified | Handler: heimdall | Date: 2026-10-18

## PROBLEM
[Hallazgo auditoria BLP-022 / F4] identity.record: filed_in_brain se marca True inmediatamente despues de crud_add al brain, sin inspeccionar el dict devuelto; una escritura al brain que retorne {'error': ...} se reporta como filed y el handler devuelve OUT-WORK con destination=brain aunque nada se haya persistido. Esperado: comprobar 'error' en el resultado de crud_add antes de marcar filed_in_brain (y degradar a DESTINATION_NOT_ALLOWED si falla y el contrato tambien rechaza).

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T19:03:39Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

FIXED (T-035): filed_in_brain = "error" not in brain_result; si ninguna ruta persiste -> DESTINATION_NOT_ALLOWED. Test test_identity_record_rejects_when_no_destination_persists.

## UPDATE 2026-10-22

VEREDICTO AUDITOR (Heimdall, read-only) 2026-10-22: CONFORME. handlers/cortex/learning.py:225 fija filed_in_brain = "error" not in brain_result y :232 degrada a DESTINATION_NOT_ALLOWED cuando ninguna ruta persistio; el handler ya no reporta filed sin inspeccionar el dict devuelto. Test test_identity_record_rejects_when_no_destination_persists pasa. Sin hallazgos. Se marca verified.

## UPDATE 2026-10-22

Verificado por verificacion del auditor Heimdall (ref E-1923). Cerrado.
