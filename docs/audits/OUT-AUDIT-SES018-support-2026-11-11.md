# OUT-AUDIT — SES018 · ARQUX · SUPPORT · 2026-11-11

**Auditor:** Heimdall (role=AUDITOR, read-only)
**Executor:** Alfred (role=GOVERNOR)
**Scope:** 3 issues de soporte triaged en CYCLE-15 (T-003, T-004, T-005)
**Método:** verificación independiente — diff review + ejecución propia de tests y probes. No se confió en la evidencia del ejecutor.

---

## Issue 1 — `2026-11-02-errores-de-handler-verbose-vuelcan-el-catalogo-c` (low)

**Veredicto: CUMPLE**

| Check | Resultado |
|---|---|
| `@server.call_tool(validate_input=False)` presente | PASS |
| Validación jsonschema propia sobre `spec.input_schema` del REGISTRY | PASS |
| Salida real `_validate_arguments(project.bind, role=__INVALID__)` | `ERROR code=INVALID_ARGS handler=project.bind field=role value='__INVALID__' valid=['governor','executor','auditor'] example=role=governor` — plana, sin `isError` → sin volcado de catálogo |
| Resolución de nombres namespaced + NOT_FOUND legible | PASS (diff) |
| `jsonschema` 4.26.0 en uv.lock | PASS — obs: dependencia transitiva del SDK MCP, convendría declararla directa |
| Tests ejecutados por el auditor | 78 passed (`test_server_call_tool.py` + `test_cortex_crud.py`) |

## Issue 2 — `2026-11-02-sin-ruta-mcp-para-mutar-el-glosario-0-de-un-cort` (medium)

**Veredicto: CUMPLE**

Probe independiente sobre copia temporal de `alfred.cortex` — 9/9 checks PASS:

- `crud_read("$0/GSIG:LNG")` → 1 entry, `section="$0"`
- `crud_update("$0/GSIG:DESC", set_={risk:M})` → ok, persiste tras re-parse
- `_parse_patches("$0/GSIG:AXM{...}")` → selector `"$0/GSIG:AXM"` (ruta `cortex.patch` cubierta)
- `crud_add("$0","GSIG","AUD",...)` / `crud_list(section="$0")` / `crud_delete` → ok
- Sin sección `$0` duplicada; `doc["sections"]` intacto; round-trip `cortex_to_dict` correcto

Diff review `crud.py`: `_find_section` resuelve `$0`→`doc["glossary"]`; `_section_entries`/`_set_section_entries`/`_section_id` unifican `symbols` vs `entries` en select/add/update/delete/move/list; `add_entry` materializa el glosario solo si falta y rechaza `glossary` no-dict (sin corrupción silenciosa); `list_entries(section=None)` no incluye glosario (comportamiento previo preservado); `_` sigue rechazado. `_crud.py`: `_resolve_legacy_selector` y `_select_all_sections` incluyen `glossary.symbols` (selector legado `GSIG:name` → `$0/GSIG:name`).

**Observación (preexistente, no regresión):** ids de sección decimales (`$0.1`, presente en `alfred.cortex`) no son direccionables por selectores — limitación del regex `\$\d+` ya existente.

Tests: `TestGlossaryCrud` +13 en `test_cortex_crud.py`; suite completa **2664 passed**, 2 skipped (faster_whisper ausente — ambiental), ruff limpio.

## Issue 3 — `2026-11-02-arqux-no-puede-consumir-codec-cortex-1-0-faltan-.issue` (high)

**Veredicto: CUMPLE** (como evaluación técnica verificada)

Verificado contra `codec_cortex 1.0.0` instalado (editable, CODEC-CORTEX@e0e7aa9):

| Superficie | Presente |
|---|---|
| `parse_cortex`, `canonicalize`, `hash_cortex` | SÍ |
| `render_hcortex`, `compile_hcortex`, `render/compile_hcortex_slots` | SÍ |
| slots/slotparser/slotc14n, `migrate_inspect/plan/apply/verify/rollback` | SÍ |
| **`validate`** | **NO** |
| **`render_hcortex_read`** | **NO** |
| **`cortex.crud.selectors`** | **NO** (y sin uso en ArqUX) |

`parse_cortex` exige `$0:format` (G010_FORMAT_REQUIRED) → no es drop-in para dialecto legacy.

Impacto en ArqUX confirmado en código:
- `cortex.verify` / `cortex.render` / `cortex.read(mode=hcortex)` → `RuntimeError` → `CortexOUT MISSING_DEPENDENCY` (fallo limpio).
- `_cc_validator=None` → validación de `brain.cortex`/`meta-brain.cortex` en `cortex_write`/`_write_mutated` se salta en silencio (se pierde la red E0xx — documentado).
- `migrate_cortex_file` → `RuntimeError` limpio; sin callers en producción.
- **Todas las mutaciones** (`entry.add/update/delete/move`, `cortex.patch`, issues/tasks/blueprints) usan reader/writer/CRUD nativos → NO afectadas.

**Conclusión:** el issue es parcialmente cierto — faltan 3 contratos pero el núcleo de gobernanza no depende del codec. Opciones documentadas: **A)** pin `codec-cortex 0.6.x` (status quo); **B)** adoptar 1.0 portando `validate`/`render_hcortex_read` a ArqUX (recomendado como dirección, coherente con BLP-005); **C)** híbrido (descartable); **D)** esperar surfaces en 1.x. **La decisión de adopción queda para el Arquitecto.**

Extra verificado: fix del path REF en `test_cortex_invalid_column_conformance.py` (validator archivado en `archive/2026-11/tools-legacy` por la reorganización 1.0) — 8 passed.

---

## Resumen

| Issue | Severidad | Veredicto |
|---|---|---|
| Errores verbose INVALID_ARGS | low | CUMPLE |
| CRUD glosario `$0` | medium | CUMPLE |
| Evaluación codec-cortex 1.0 | high | CUMPLE |

**Observaciones no bloqueantes:**
1. `jsonschema` es dependencia transitiva (SDK MCP), no declarada directa en pyproject.
2. Selectores no direccionan secciones decimales (`$0.1`) — preexistente.
3. Bajo codec 1.0, la validación de brains en escrituras se omite silenciosamente.
4. La elección de adopción codec-cortex 1.0 (opción A/B/C/D) requiere decisión del Arquitecto.

**Sin commits, sin push, sin publicación** — working tree contiene los cambios sin versionar, según lo autorizado.

---

# ADDENDUM — Auditoría retroactiva de 9 issues en `fixed` (misma sesión)

**Alcance:** issues `fixed` pendientes de verificación al inicio de SES018.
**Método:** verificación independiente — probes en vivo + diff/code review + re-ejecución de tests.

| # | Issue | Veredicto | Evidencia del auditor |
|---|---|---|---|
| 1 | context.cortex puntero CTX | CUMPLE | Archivo vivo canónico: `$0` declara `CTX/context/attrs`; entrada `CTX:heimdall{project,scope,agent,ses,project_root}` attrs; contenido actual refleja SES018/Heimdall (escrito por la propia sesión auditada) |
| 2 | doctor falso positivo cycles | CUMPLE | `arqux doctor` en workspace root: `context=workspace`, 8 checks, SIN exigencia de `cycles` (estructura espera 4 dirs workspace); en proyecto: `context=project`, 9 checks. Checks warnings residuales = hallazgos reales documentados (residue .lock) |
| 3 | barrido 497 errores brains | CUMPLE PARCIAL | `cortex.verify` live sobre CODEC-CORTEX brain: `valid=true`, 183 entries, 13 sections — E008 dedupe confirmado. E032/E034 pendientes de criterio humano por proyecto = estado honesto declarado, no defecto del fix (requiere BLP por proyecto, decisión del Arquitecto) |
| 4 | entry.add renombre silencioso | CUMPLE | `_next_number` deriva sufijo del contenido del archivo (max `{base}_NNNN`+1 vía crud_list), no de contador de proceso; campos `renamed`/`requested` explícitos en OUT-WORK; test de regresión presente |
| 5 | timelog unbound tras reinicio | CUMPLE (alcance honesto) | `session.close` pasa `session_ref` a `observe()`; `unbound_warning()` emite el comando exacto de re-vinculación; items fuera de alcance (tw_log ledger, adaptador Teamwork) documentados como otro repo |
| 6 | puntero global → checkpoint | CUMPLE | commit `1b679a7` existe; `_project.py` define `CONTEXTS_DIR="contexts"` (punteros por ejecución); `tests/test_t046_context_pointer_precedence.py` pasa |
| 7 | SESSION_IN_USE re-adherir | CUMPLE | `open_session(intent='resumed')` re-liga vía `_bind` (política 2026-10-28); `test_t039_session_reentry.py` pasa; la re-adhesión SES017→SES018 es mecanismo vivo |
| 8 | lecciones conductuales identidad | CUMPLE | Los 7 puntos BLP-020 verificados en código comiteado: `entry_kind` + exención en `require_writable_destination`, routing por kind en `learning.py`, `drop_identity_lesson_e023` con regex de título BEHAVIORAL LESSONS, fix reader GSIG/GCON round-trip, `GSIG:LNG` declarada en identidad, skills actualizadas, evento `pending_loop` en context_set. `test_blp020_identity_lessons.py` pasa |
| 9 | skills learning/protocol desactualizadas | CUMPLE | `learning.skill.md` refleja routing real (conductual→identidad BEHAVIORAL LESSONS curada; resto→brain $7; `AXM:identity_is_curated`); paridad workspace==packaged confirmada byte-idéntica por el hook de homologación |

**Veredicto global: 9/9 CUMPLE** (8 completos + 1 parcial honestamente declarado con pendiente explícito del Arquitecto).

**Observación nueva (no bloqueante):** las entradas `LOOP:*` del registro de loops autónomos (BLP-023, brain §18) producen warnings `E017_UNPARSED_LINE` bajo `cortex.verify` del codec legacy — `valid=true` se mantiene pero hay ruido en el validador. Candidato: declarar el sigilo LOOP en el glosario del brain o evaluar en la decisión codec-cortex 1.0.
