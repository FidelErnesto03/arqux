# ISSUE: [Higiene workspace T-032] identity.record rompe el archivo de identidad (nivel 1) en DOS formas, verificado en vivo: (1) escribe la leccion como LNG en un archivo que infer_document_kind() clasifica 'skill' (tiene AXM y no tiene WRK; el IDN:alfred no aporta kind y el filename tampoco), disparando E023_LEVEL1_LIVE_STATE + I001_UNDECLARED_SIGIL (LNG no declarado en $0) -> el archivo queda valid=false. (2) La escritura DESCARTA las 4 declaraciones GSIG de $0: el archivo paso de 16 entradas (4212 B, incluyendo GSIG:IDN/AXM/LIM/DESC) a 13 entradas (5321 B, GSIG count=0), perdiendo la autodescripcion del glosario. Evidencia: .arqux/identities/alfred.cortex (restaurado del canonico tras el hallazgo), backups en .arqux/archive/hygiene-2026-10-18/rollback/. Contexto: la identidad del workspace acumulaba 325 entradas / 320 errores (313 E023) por este mismo mecanismo - cada leccion registrada invalidaba el contrato nivel 1 y engordaba el archivo hasta 195KB. Esperado: (a) identity.record debe escribir la leccion en un artefacto apropiado (brain de proyecto / meta-brain como LNG/KNW, o una seccion de lessons declarada en el glosario), NO en el contrato nivel 1; (b) prohibir E023 en la escritura en vez de dejar el archivo invalido; (c) preservar las GSIG al reescribir.
# Severity: high | Status: verified | Handler: Alfred | Date: 2026-10-18

## PROBLEM
[Higiene workspace T-032] identity.record rompe el archivo de identidad (nivel 1) en DOS formas, verificado en vivo: (1) escribe la leccion como LNG en un archivo que infer_document_kind() clasifica 'skill' (tiene AXM y no tiene WRK; el IDN:alfred no aporta kind y el filename tampoco), disparando E023_LEVEL1_LIVE_STATE + I001_UNDECLARED_SIGIL (LNG no declarado en $0) -> el archivo queda valid=false. (2) La escritura DESCARTA las 4 declaraciones GSIG de $0: el archivo paso de 16 entradas (4212 B, incluyendo GSIG:IDN/AXM/LIM/DESC) a 13 entradas (5321 B, GSIG count=0), perdiendo la autodescripcion del glosario. Evidencia: .arqux/identities/alfred.cortex (restaurado del canonico tras el hallazgo), backups en .arqux/archive/hygiene-2026-10-18/rollback/. Contexto: la identidad del workspace acumulaba 325 entradas / 320 errores (313 E023) por este mismo mecanismo - cada leccion registrada invalidaba el contrato nivel 1 y engordaba el archivo hasta 195KB. Esperado: (a) identity.record debe escribir la leccion en un artefacto apropiado (brain de proyecto / meta-brain como LNG/KNW, o una seccion de lessons declarada en el glosario), NO en el contrato nivel 1; (b) prohibir E023 en la escritura en vez de dejar el archivo invalido; (c) preservar las GSIG al reescribir.

## CONTEXT
reported_by: Alfred
reported_at: 2026-10-18T18:18:57Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-18

Triageado: bug de handler con corrupcion silenciosa (invalida nivel 1 y descarta GSIG). Va a BLP prioritario.

## UPDATE 2026-10-18

FIXED (pendiente verdicto del auditor): identity.record no escribe LNG en un contrato nivel-1 con AXM; persiste en el brain del proyecto o rechaza DESTINATION_NOT_ALLOWED. El contrato queda byte-identico, sin E023/I001 y con las 4 GSIG preservadas. Tests: test_identity_destination_rejects_live_state_sigil, test_identity_destination_does_not_corrupt_a_level1_contract. Evidencia E-1840/E-1841.

## UPDATE 2026-10-18

Verified por verdicto E-1858 (heimdall): identity.record no escribe LNG en un contrato nivel-1 con AXM; persiste en el brain o rechaza DESTINATION_NOT_ALLOWED; el contrato queda byte-identico con las 4 GSIG. Tests test_identity_destination_rejects_live_state_sigil / test_identity_destination_does_not_corrupt_a_level1_contract.
