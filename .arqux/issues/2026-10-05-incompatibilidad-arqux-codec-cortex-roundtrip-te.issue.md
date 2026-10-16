# ISSUE: Incompatibilidad ARQUX<->codec-cortex (roundtrip): tests/test_cortex_writer.py falla 11 casos (test_roundtrip_basic/multiple_entries/cuerpo/string_escaping/booleans_integers/none_skipped/empty_section/section_no_title/section_comments/multiple_sections/list_attr_as_string). El parser local (../CODEC-CORTEX/codec_cortex/parser.py) rechaza la salida de ArqUX: I001_UNDECLARED_SYMBOL 'ARQX' (linea ARQX:artifact{level:\"2\", name:\"brain\"}), y usa cortex_version 0.1 con secciones de id entero/glosario simbólico distinto. Pre-existente e independiente de BLP-016. Requiere alinear el writer de ArqUX con el codec nuevo (o el codec con ArqUX) en el proyecto CODEC-CORTEX (CYCLE-01 Fundacion limpia).
# Severity: medium | Status: verified | Handler: alfred | Date: 2026-10-05

## PROBLEM
Incompatibilidad ARQUX<->codec-cortex (roundtrip): tests/test_cortex_writer.py falla 11 casos (test_roundtrip_basic/multiple_entries/cuerpo/string_escaping/booleans_integers/none_skipped/empty_section/section_no_title/section_comments/multiple_sections/list_attr_as_string). El parser local (../CODEC-CORTEX/codec_cortex/parser.py) rechaza la salida de ArqUX: I001_UNDECLARED_SYMBOL 'ARQX' (linea ARQX:artifact{level:\"2\", name:\"brain\"}), y usa cortex_version 0.1 con secciones de id entero/glosario simbólico distinto. Pre-existente e independiente de BLP-016. Requiere alinear el writer de ArqUX con el codec nuevo (o el codec con ArqUX) en el proyecto CODEC-CORTEX (CYCLE-01 Fundacion limpia).

## CONTEXT
reported_by: alfred
reported_at: 2026-10-05T16:19:05Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-05

Triaje: severidad medium. Requiere alinear el writer de ArqUX con el codec-cortex nuevo (cortex_version 0.1, glosario simbólico) o viceversa. Pertenence al proyecto CODEC-CORTEX (CYCLE-01 Fundacion limpia), no al writer de gobernanza de ArqUX. Bloqueante para los tests test_cortex_writer (11). No hay cambios en ArqUX pendientes; se resuelve en CODEC-CORTEX.

## UPDATE 2026-10-10

Resuelto en el escritor ArqUX y en la compatibilidad del parser CODEC-CORTEX. write_cortex_from_json emite $0:format{cortex:"0.1", encoding:"UTF-8"} y declaraciones GSIG compatibles; CODEC-CORTEX normaliza GSIG heredado a SymbolDef. Se cubrieron mixed attrs/cuerpo sin fallar el round-trip. Evidencia: PYTHONPATH=src python -m pytest -q => 1882 passed, 16 skipped; prueba directa codec_cortex.parse_cortex sobre salida ArqUX => símbolos LNG y entradas parseadas correctamente. Sin cambios destructivos ni commit.
