# CORTEX 1.0 — Catálogo de Errores Cerrado

**Estado:** 1.0 (ratificado con CORTEX-SPEC-1.0 el 2026-11-14; compañero de §9)
**Invariante:** catálogo == emitidos ∪ reservados-declarados. Generado mecánicamente del código fuente de las 5 superficies (2026-11-01).

## Mapa código ↔ emisor ↔ superficie

| Código | python | go | node | rust | bash |
|---|---|---|---|---|---|
| G002_GLOSSARY_REOPENED | x | x | x | x | x |
| G004_GLOSSARY_DECLARATION_MUST_BE_ATTRS | x | x | x | x | x |
| G005_FORMAT_REQUIRED | — | — | — | — | x |
| G006_DUPLICATE_FORMAT | x | x | x | x | x |
| G007_UNSUPPORTED_VERSION | x | x | x | x | x |
| G008_INVALID_CONTRACT | x | x | x | x | x |
| G010_FORMAT_REQUIRED | x | — | — | — | — |
| G011_ENCODING_REQUIRED | x | x | x | x | x |
| G012_INVALID_MICRO | x | x | x | x | x |
| G014_INVALID_ENUM | x | x | x | x | x |
| G015_DUPLICATE_SYMBOL | x | x | x | x | — |
| G016_SYMBOL_TYPE_REQUIRED | x | x | x | x | x |
| G017_UNKNOWN_SHAPE | x | x | x | x | x |
| G018_SYMBOL_WEIGHT_REQUIRED | x | x | x | x | x |
| G019_INVALID_WEIGHT | x | x | x | x | x |
| G020_SYMBOL_DESCRIPTION_REQUIRED | x | x | x | x | x |
| G021_ATTRS_CONTRACT_REQUIRED | x | x | x | x | x |
| G022_POSITIONAL_CONTRACT_REQUIRED | x | x | x | x | x |
| G023_RELATION_CONTRACT_TOO_SHORT | x | x | x | x | x |
| G024_FOCUS_REQUIRED | x | x | x | x | x |
| G025_UNKNOWN_FOCUS_FIELD | x | x | x | x | x |
| G026_UNKNOWN_ENUM_REFERENCE | x | x | x | x | x |
| G030_SIGIL_MAP_REQUIRED | x | x | x | x | x |
| G031_DUPLICATE_SIGIL_MAP | x | x | x | x | x |
| G032_INVALID_SIGIL_MAP | x | x | x | x | x |
| G033_SLOT_CONTRACT_REQUIRED | x | x | x | x | x |
| G034_SLOT_CONTRACT_GAP | x | x | x | x | x |
| G035_DUPLICATE_SLOT_POSITION | x | x | x | x | x |
| G036_DUPLICATE_SLOT_NAME | x | x | x | x | x |
| G037_SLOT_FOCUS_UNRESOLVED | x | x | x | x | x |
| G038_SLOTS_OPEN_FORBIDDEN | x | x | x | x | x |
| G039_ENCODING_SHAPE_MISMATCH | x | x | x | x | x |
| G040_CONTRACT_SURFACE_CONFLICT | x | x | x | x | x |
| G041_SIGIL_MAP_ORDER | x | x | x | x | x |
| G042_GLOSSARY_HEADER_INVALID | x | x | x | x | x |
| H400 | x | x | x | x | x |
| H401 | x | x | x | x | — |
| H401_MISSING_ENVELOPE | x | x | x | x | — |
| H401_UNSUPPORTED_HCORTEX_VERSION | x | x | x | x | — |
| H402 | x | x | x | x | — |
| H403_MISSING_GLOSSARY_BLOCK | x | x | x | x | — |
| H410 | x | x | x | x | — |
| H411 | x | x | x | x | — |
| H414 | x | x | x | x | — |
| H420 | x | x | x | x | — |
| H431 | x | x | x | x | — |
| H432 | x | x | x | x | — |
| H433 | x | x | x | x | — |
| H441 | x | x | x | x | — |
| H460 | x | x | x | x | — |
| H461 | x | x | x | x | — |
| H481 | x | x | x | x | — |
| H481_HIDDEN_COPY | x | x | x | x | — |
| H482 | x | x | x | x | — |
| H490 | x | x | x | x | — |
| I001_UNDECLARED_SYMBOL | x | x | x | x | x |
| I002_DUPLICATE_IDEA_ADDRESS | x | x | x | x | x |
| I004_SHAPE_DELIMITER_MISMATCH | x | x | x | x | x |
| I005_UNKNOWN_FIELD | x | x | x | x | — |
| I006_DUPLICATE_FIELD | x | x | x | x | — |
| I006_DUPLICATE_IDEA_ADDRESS | x | x | x | x | x |
| I008_REQUIRED_FIELD_MISSING | x | x | x | x | — |
| I010_ENUM_VIOLATION | x | x | x | x | x |
| I012_POSITIONAL_ARITY | x | x | x | x | x |
| I023_UNKNOWN_FIELD_TYPE | x | — | — | — | — |
| I050_SLOT_NOT_ALLOWED_IN_GLOSSARY | x | x | x | x | — |
| I051_DUPLICATE_SLOT | x | x | x | x | — |
| I052_UNKNOWN_SLOT | x | x | x | x | x |
| I053_MISSING_REQUIRED_SLOT | x | x | x | x | x |
| I054_SLOT_OUT_OF_ORDER | x | x | x | x | x |
| I055_NAMED_ATTR_IN_SLOT_IDEA | x | x | x | x | x |
| I056_PIPE_PAYLOAD_IN_SLOT_IDEA | x | x | x | x | x |
| I057_SLOT_INDEX_LIMIT | x | x | x | x | x |
| I057_SLOT_INDEX_OUT_OF_RANGE | — | x | x | — | — |
| I058_MIXED_SURFACE_VERSION | x | x | x | — | — |
| L001_INVALID_SYMBOL | x | x | x | x | x |
| L003_INVALID_KEY | x | x | x | x | x |
| L005_INVALID_STRING | x | x | x | x | x |
| L007_INVALID_LIST | x | x | x | x | x |
| L008_UNCLOSED_BRACE | — | — | x | — | — |
| L010_INVALID_ATOM | x | x | x | x | x |
| L020_HOMOGLYPH_MARKER | — | x | x | — | — |
| L020_INVALID_SLOT_MARKER | x | x | x | x | x |
| L021_INVALID_SLOT_INDEX | x | x | x | x | x |
| L022_SLOT_INDEX_ZERO | — | x | x | — | — |
| L022_SLOT_ZERO_FORBIDDEN | x | x | x | x | — |
| L023_SLOT_INDEX_LEADING_ZERO | — | x | x | — | — |
| L023_SLOT_LEADING_ZERO | x | x | x | x | — |
| L024_SLOT_INDEX_SEPARATOR | — | x | x | — | — |
| L024_SLOT_SEPARATOR_REQUIRED | x | x | x | x | — |
| L402_COMMENT_DROPPED | x | x | x | x | — |
| L403_INTRALINE_WHITESPACE | x | x | x | x | — |
| L405_OPEN_ATTR_ORDER | x | x | x | x | — |
| L406_COMPILE_SIDE_DROP | x | x | x | x | — |
| L499_UNCLASSIFIED_LOSS | x | x | x | x | — |
| S002_DUPLICATE_SECTION | x | x | x | x | — |
| S003_INVALID_IDEA_HEAD | x | x | x | x | x |
| S005_CONTENT_OUTSIDE_SECTION | x | x | x | x | x |
| S006_INVALID_ATTRS | x | x | x | x | x |
| S007_UNCLOSED_BODY | x | x | x | x | — |
| S999 | x | x | x | — | — |
| S999_INTERNAL_PARSE_FAILURE | x | x | x | x | x |
| U001_BOM_FORBIDDEN | x | x | x | x | x |
| U003_NON_ASCII_IDENTIFIER | x | x | x | x | x |

## Pérdidas declaradas HCORTEX (L4xx)

Catálogo cerrado §8.2 de la spec 1.0. Cada pérdida se emite desde el comando `loss-report` en las cinco superficies (Python, Go, Node, Rust, Bash) con salida byte-idéntica.

| Código | Pérdida | Emisor |
|---|---|---|
| L402_COMMENT_DROPPED | Comentarios `#` (dentro o fuera del glosario) | loss-report (python, go, node, rust, bash) |
| L403_INTRALINE_WHITESPACE | Whitespace intra-línea no significativo | loss-report (python, go, node, rust, bash) |
| L405_OPEN_ATTR_ORDER | Orden editorial de attrs en sigilos `open:true` | loss-report (python, go, node, rust, bash) |
| L406_COMPILE_SIDE_DROP | Idea del AST perdida en el roundtrip render→compile: su header renderizado (`### ns::SIGIL:name`) no vuelve a parsear, de modo que la idea desaparece sin diagnóstico (error, exit 1) | loss-report (python, go, node, rust) |
| L499_UNCLASSIFIED_LOSS | Divergencia de roundtrip no clasificable (error, exit 1) | loss-report (python, go, node, rust, bash) |

**Nota L406 (2026-11-14):** clasifica un caso antes reportado como `L499`. Disparador demostrado: un namespace con `.`/`-` (p. ej. `tenant.x::KNW:alpha`) produce un marcador `### tenant.x::KNW:alpha` que el `_IDEA_MARKER_RE` de Python/Go/Node/Rust no reconocía (`\w+::`), perdiendo la idea; Bash sí lo reconocía. **Divergencia resuelta**: el marcador HCORTEX de las cuatro superficies se alineó a la gramática CORTEX (namespace `[a-z][a-z0-9_.-]*`, nombre imprimible sin espacio/`{}`/`|`), de modo que la idea ya no se pierde y **las cinco superficies vuelven a coincidir** (verificado). L406 queda como **guardia clasificada** —sucesor específico de `L499`— para cualquier pérdida render→compile futura; hoy no tiene disparador en el corpus certificado.

Cada pérdida emite entrada loss-report conforme a `docs/schemas/loss-report-1.0.schema.json`.

**Retirados como pérdida (2026-11-14, §8.3 de la spec):** `L401` (marcador de fence en bloque: roundtrip intacto en las cinco superficies) y `L404` (CAPA ausente: ausencia preservada; `resolve_capa()` es derivado). Ver evidencia en la spec §8.3.

## Precedencia de diagnósticos (una misma línea)

Cuando una línea viola varias reglas, se emite **un solo** diagnóstico, según este orden determinista (fijado por el orden de verificación del parser):

1. `S003_INVALID_IDEA_HEAD` — la línea no tiene forma de idea (se comprueba primero).
2. `U003_NON_ASCII_IDENTIFIER` — el nombre no es ASCII imprimible (antes de resolver el sigilo).
3. `I001_UNDECLARED_SYMBOL` — el sigilo no está declarado en el glosario.
4. `I006_DUPLICATE_IDEA_ADDRESS` / `I004_SHAPE_DELIMITER_MISMATCH` — dirección duplicada o delimitador de forma incorrecto.
5. `I006_DUPLICATE_FIELD` (y validación de contrato) — dentro del payload.

Verificado por `tests/test_diagnostics.py` (Python) y por los portes de cada superficie.

## Códigos reservados y colisiones conocidas

- `I006` colisiona en el codigo: `I006_DUPLICATE_FIELD` (attrs) e `I006_DUPLICATE_IDEA_ADDRESS` (direccion). Defecto conocido: la implementacion los distingue por contexto; una revision futura debe reasignar uno.
- `X002_REQUIRED_EXTENSION_UNSUPPORTED`, `I049`, `L025_TRAILING_COMMA`: citados en spec/skill pero SIN emisor — `reserved` (detectables, pendiente implementar o retirar).
- `L401_FENCE_MARKER` (histórico, sin nombre de familia): `reserved` para el dialecto 0.1 legacy — retirado como pérdida 1.0 en §8.3.
- `P17`: emisor real en slots.py (trailing comma) — fuera del esquema de familias; documentado aqui como codigo vigente.
- `HLOSS001_OPEN_EXTRA_FIELD` … `HLOSS007_BODY_BOUNDARY_WHITESPACE`: diagnósticos **legacy** de `explain-loss` (Go, `cortex/loss.go`), no normativos. Las filas `S001`–`S007` que los citaban sin prefijo se retiraron el 2026-11-14: el emisor real lleva prefijo `HLOSS` y pertenece a la superficie 0.1 histórica, no al catálogo 1.0.

## Códigos reservados

Espacio G0xx reservado para meta-declaraciones futuras; I05x para slots; L4xx para pérdida declarada. Un código reservado sin emisor se lista aquí, nunca implícito.
