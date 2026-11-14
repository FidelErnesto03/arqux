# TEST-SUITE-FRAMEWORK — Suite de pruebas derivada de la evidencia

**Documento:** `TEST-SUITE-001`
**Versión:** `0.1`
**Fecha:** `2026-11-13`
**Autor:** Alfred — mandato del Arquitecto
**Principio:** ninguna prueba se inventa. Cada test deriva de una **fricción relevada**, una
**lección registrada** o un **issue cerrado** — y lleva su procedencia en el nombre o el docstring.

---

## 0. Doctrina

1. **Regresión obligatoria:** todo defecto encontrado produce un test que falla sin el fix.
2. **La suite paga su costo:** los tests descubren defectos reales, no solo los congelan.
3. **Brechas declaradas, no silenciadas:** una capacidad ausente es un `xfail` con motivo; cuando
   se implemente, el test XPASA y obliga a convertirlo en requisito duro.
4. **Se verifica el artefacto, nunca el `ok`:** toda aserción mira el archivo/estado escrito.
5. **Determinismo:** sin red, sin relojes dependientes, sin estado heredado (fixtures `tmp_path`).

---

## 1. Mapa fuente → prueba

### 1.1 · Revisión de ergonomía 2026-11 (`CODEC-CORTEX/docs/CORTEX-DB-ERGONOMICS-REVIEW-2026-11.md`)

| # | Fricción | Prueba | Archivo | Estado |
|---|---|---|---|---|
| 2.1 | Rampa de escritura con reglas tácitas | `test_unbraced_attrs_value_is_accepted`, `test_name_collision_is_reported_never_silent` | `tests/e2e/test_ergonomics_contract.py` | ✅ |
| 2.2 | Dry-run miente; métricas asimétricas | `test_patch_dry_run_fails_where_apply_fails`, `test_entry_add/update_file_bytes_describe_the_real_file` | `tests/e2e/test_ergonomics_contract.py` | ✅ (defecto real corregido) |
| 2.3 | Éxitos silenciosos (checkpoint vacío) | `test_empty_checkpoint_is_rejected_and_preserves_state` | `tests/e2e/test_ergonomics_contract.py` | ✅ |
| 2.5 | Muros de sesión/identidad | `test_switch_works_from_workspace_root`, `test_second_session_error_presents_alternatives`, `test_claim_without_bound_session_is_guided` | `tests/e2e/test_identity_session.py` | ✅ (defecto real corregido) |
| 2.6 | No existe consulta transversal | `test_cross_corpus_query_exists` | `tests/e2e/test_ergonomics_gaps.py` | ⚠️ xfail declarado |
| 2.8 | Contratos CLI divergentes | `test_first_level_project_and_cycle_commands_exist`, `test_call_accepts_file_payload`, `test_call_quiet_failure_sets_nonzero_exit` | `tests/e2e/test_transport_cli.py` | ✅ |
| 2.9 | Validador centrado en brains; migración no repara | `test_migration_reports_content_repairs` | `tests/e2e/test_ergonomics_gaps.py` | ⚠️ xfail declarado |
| 2.10 | Gates tardíos | `test_ready_reports_all_pending_placeholders_at_once` | `tests/e2e/test_integrity_gates.py` | ✅ |
| 2.11 | Errores en códigos, no humanos | `test_cycle_synthesize_without_braces_explains_the_expected_form`, `test_patch_failure_reports_selector_and_reason`, `test_cycle_synthesize_reports_hint_for_unbraced_content` | `test_ergonomics_contract.py`, `test_transport_cli.py` | ✅ |
| 2.12 | Backlog del codec (U4 emit, U7, U10) | `test_public_emit_helper_is_exported` | `tests/e2e/test_ergonomics_gaps.py` | ⚠️ xfail declarado |
| 1.1 | Restauración determinista de contexto | `test_switch_dry_run_is_read_only` + espejo en `test_signal_quality` | `test_identity_session.py` | ✅ |
| 1.5 | Separación de roles | `test_forbidden_role_cannot_execute` | `tests/e2e/test_security_controls.py` | ✅ |

### 1.2 · Lecciones registradas

| Lección | Qué exige | Pruebas | Estado |
|---|---|---|---|
| `verifier_signal_noise` | salud = E==0; W deduplicado; sin W001 por entrada | `test_healthy_brain_has_no_w001_name_noise`, `test_real_corruption_is_flagged_not_buried` | ✅ |
| `silent_corruption` | ningún `ok` con artefacto dañado | `tests/test_cortex_write_transaction.py` (14 tests), `test_blueprint_update_rejects_structural_markers_in_content`, `test_cycle_synthesize_treats_backslashes_literally` | ✅ |
| `contextual_identity` | identidad desde la sesión, no del transporte | `test_claim_records_active_session_identity` | ✅ |
| `dos_controles_de_seguridad_distintos` | allow-list y confinamiento de raíz, ambos | `test_undeclared_action_is_denied`, `test_declared_action_outside_root_is_denied`, `test_declared_action_inside_root_succeeds` | ✅ |
| `verificar_comportamiento_no_registro` | "registrado" no es "ejecutando" | `test_declared_action_inside_root_succeeds` (verifica efecto en FS) | ✅ |
| `defecto_no_es_decision` | (conductual — no automatizable directamente) | — | 📝 revisión humana |
| `layers` | capacidad sobrevive sin ArqUX | cubierto por `test_security_controls` (ejecutor independiente del marco) | ✅ parcial |

### 1.3 · Issues cerrados como regresión

| Issue (origen) | Defecto | Prueba |
|---|---|---|
| 2026-11-13 kernel | `entry_add` trunca cuerpos con `clave: valor` | `tests/test_cortex_write_transaction.py` (suite completa) |
| Manhattan CYCLE-04 D1 | `blueprint_update` duplica/fusiona markers | `test_blueprint_update_rejects_structural_markers_in_content` |
| Manhattan CYCLE-04 D2 | `cortex_entry_update` parte valores por comas internas | cubierto por suite de integridad (attrs fantasma) |
| CYCLE-14/BLP-001 | escrituras concurrentes perdidas (~55%) | `test_concurrent_adds_do_not_lose_writes` |
| 2026-10-01 | `cycle.synthesize` expande backrefs `re.sub` | `test_backslash_payload_survives_synthesis` |
| 2026-10-02 | `blueprint.claim` usa identidad del transporte | `test_claim_records_active_session_identity` |
| 2026-10-11 dogfood | error opaco, sin `@file`/stdin, sin subcomandos | `tests/e2e/test_transport_cli.py` (5 tests) |

---

## 2. Defectos reales descubiertos por esta suite (y corregidos)

| Defecto | Fricción | Fix |
|---|---|---|
| `cortex.patch` aprobaba en dry-run selectores inexistentes | 2.2 | dry-run resuelve cada selector con `crud_read`; sin coincidencias → `failed` |
| `identity.switch` desde la raíz del workspace resolvía la identidad pero entregaba el handoff a la raíz → `NOT_FOUND` opaco | 2.5 / 2.11 | el handoff usa el `project_root` del puntero de contexto; error con remediación explícita |

### 2.1 · Hallazgos de la auditoría Heimdall (2026-11-13, read-only)

| ID | Hallazgo | Severidad | Fix verificado |
|---|---|---|---|
| HD-01 | La guarda enmascaraba daño colateral cuando el mismo `SIGIL:name` vivía en dos secciones | ALTO | Secciones permitidas resueltas **antes** de mutar (`crud_read` sobre el selector); nunca por nombre. Tests: `test_guard_detects_collateral_on_same_name_in_other_section`, `test_update_with_section_selector_does_not_authorise_other_section` |
| HD-02 | Cifras del BLP desactualizadas | MEDIO | Cifras medidas al momento de la firma (este documento y BLP-024 §3/§12/§13) |
| HD-03 | El schema MCP de `blueprint.synthesize` descartaba `content` y la implementación lo ignoraba | MEDIO | `content` expuesto en `input_schema` y **aplicado** (escritura marker-safe, `sections_written`). Tests: `test_blueprint_synthesize_schema_exposes_content`, `test_synthesize_with_content_actually_writes_sections` |
| HD-04 | `blp_markers@` escrito como YAML inválido (comillas embebidas) | BAJO | Cadena CSV entre comillas (YAML válido). Test: `test_blueprint_frontmatter_is_valid_yaml` |
| HD-05 | Rollback de la guarda no atómico | BAJO | temp + `fsync` + `os.replace` |
| HD-06 | Attrs con valores con dos puntos se reclasifican como cuerpo | BAJO | Riesgo declarado (R-01); requiere regresión sobre corpus real |

**Regresión permanente del incidente del kernel (T-1.2):** `test_kernel_incident_regression` y
`test_kernel_like_document_roundtrip_preserves_every_body` reproducen el documento tipo `AGENTS.md`
y verifican que añadir a la misma sección no trunca la prosa.

---

## 3. Cómo se corre

```bash
# suite e2e (derivada de la evidencia)
./.venv/bin/python -m pytest tests/e2e -q

# suite completa del framework
PATH="$PWD/.venv/bin:$PATH" ./.venv/bin/python -m pytest tests/ -q
```

**Línea base vigente (medida al preparar 0.9.0):** `2708 passed · 2 skipped · 3 xfailed · 0 fallos reales`.
El total varía con el corpus local de `.cortex`: `tests/test_cortex_migration.py` parametriza sobre cada archivo del árbol de gobernanza.
Desglose de la suite derivada: `tests/e2e` 46 passed + 3 xfailed · `tests/test_cortex_write_transaction.py`
18 passed. El único fallo observado sin el venv en `PATH` es ambiental (`test_packaging` invoca el CLI).

---

## 4. Brechas declaradas (xfail)

1. **2.6 · consulta transversal:** no existe handler de consulta por corpus; los selectores
   direccionan un archivo. Es el desbloqueo ergonómico interno más importante (Platform).
2. **2.12/U4 · helper de emisión ideática:** no hay API pública `emit` para escribir CORTEX
   escapado; hoy se descubre leyendo el paquete.
3. **2.9 · migración que repara:** `migrate` reescribe formato pero no planifica reparación de
   contenido (E032 en 6/7 identidades post-migración).

**Regla:** cuando una brecha se cierre, el test XPASA y **debe** convertirse en requisito duro en
el mismo cambio.

---

### 1.4 · Superficies documentales (auditoría 2026-11-13)

| Superficie | Verificación | Archivo |
|---|---|---|
| Versión | pyproject = runtime = badge del README; fallback lee pyproject en vez de una constante histórica | `tests/e2e/test_docs_consistency.py` |
| Conteos | README y HANDLERS.md coinciden con `handler_count()` (111) | idem |
| Rutas | `AGENTS.md` en la raíz (no `.arqux/AGENTS.md`); PULSE dentro de `brain.cortex` (no `pulse.jsonl`) | idem |
| Instalación | `pip install --pre arqux` mientras sea pre-release | idem |
| Cambios | `CHANGELOG.md` con sección `[Unreleased]` | idem |

## 5. Próximos bloques (no cubiertos aún)

- **Property-based** (hypothesis): roundtrip parse→write→parse sobre corpus generado; fuzz de
  attrs/cuerpos con comillas, llaves y saltos.
- **Cross-runtime conformance** (Node/Bash/Go): el contrato CLI único (2.8) hoy solo se prueba en
  Python.
- **Migración real** extremo a extremo con proyecto legado.
- **Presupuesto del kernel:** límite ≤2.000 tokens y ≤40 por línea AXM (verificable por test).

---

*Cada prueba cita su fuente. Si una fuente no tiene prueba, es una brecha declarada — nunca un olvido.*
