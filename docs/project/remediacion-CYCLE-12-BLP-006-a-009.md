# Remediación CYCLE-12 — BLP-006 a BLP-009

**Fecha**: 2026-09-21
**Contexto**: Ejecución gobernada de cuatro Blueprints de remediación en
CYCLE-12, derivados del triaje formal del registro de issues (BUG-003,
BUG-004, BUG-005, find-workspace-root, resolución de tareas entre ciclos).
Cada BLP fue auditado por Heimdall antes de ejecutarse y cerrado vía los
handlers del ciclo de vida (`blueprint.ready → claim → task → ac → complete`).

Los documentos fuente de cada BLP viven en `.arqux/cycles/CYCLE-12/blueprints/`
(excluido de git por diseño de gobernanza); este documento consolida la
evidencia para el historial del repositorio.

---

## BLP-006 — Resolución determinista de tareas entre ciclos

**Defecto**: `task.read/run/claim/update/complete/fail` resolvían `T-NNN`
contra la primera coincidencia alfabética entre ciclos. Una tarea
duplicada en CYCLE-01/02/07 devolvía silenciosamente la de CYCLE-01.

**Fix** (`src/arqux/handlers/task.py`): resolver compartido
`_resolve_task_file` + `_current_cycle_id` + `_task_lookup_error`:

1. Path dentro de `.../cycles/CYCLE-XX` → solo ese ciclo.
2. Sin ciclo derivable → ciclo actual primero.
3. Coincidencia única en otro ciclo → se devuelve; **múltiples →
   `TASK_AMBIGUOUS`** listando ciclos candidatos.

**Saneamiento**: 4 artifacts `.cortex` corruptos por el bug histórico
`text=` reparados vía `write_cortex_pair`, backups `.bak-blp006`.

**Evidencia**: `tests/test_task_cycle_resolution.py` (6),
`test_import_smoke.py` (2), `test_writer_roundtrip.py` (3) — 11/11 verdes.
E2E real: `task.read T-004` → `TASK_AMBIGUOUS (CYCLE-01, CYCLE-02, CYCLE-07)`.

---

## BLP-007 — Onboarding de proyectos (BUG-005 P1–P6)

**Defectos**: `project.init` sin seed escribía un brain skeleton inválido
(E024, bloqueaba CRUD); el registro en workspace escribía texto plano en
vez de `DOM:<name>`; `cortex.entry.add` renombraba silenciosamente a
`_NNNN` incluso sin colisión; selectores de prefijo (`mi_club*`) no
funcionaban; `cortex.ref` mutaba el brain (append a PULSE); la guía de
seed no reflejaba los campos exigidos por el validador.

**Fixes**:

| Ítem | Cambio |
|---|---|
| Brain válido | `src/arqux/templates/brain.cortex` — plantilla nivel-2 con layout canónico (`$19` ARQX, `WRK:current` en `$8`, `ERR:concurrency` en `$11`); tokens `__PROJECT__`/`__GOVERNOR__`/`__DATE__`; `cortex.verify` → 0 diagnostics |
| Registro real | `_register_in_workspace` crea `projects.cortex` si falta y hace upsert de `DOM:<name>` parseable; `registered_in_workspace` refleja presencia real |
| Rename explícito | `entry.add` conserva el nombre pedido; `_NNNN` solo en colisión real, reportado vía `renamed:a->b` + campos `requested`/`renamed` |
| Wildcards | Prefijo `nombre*` soportado en `_entry_matches` y `_select_all_sections` |
| ref read-only | `cortex.ref` eliminó `_record_pulse` — brain byte-idéntico verificado por sha256 |
| Guía alineada | `STP:build_brain` documenta `REQUIRED_FIELDS` del validador (name universal, `survive`, enums status/survive) |

**Evidencia**: `tests/test_project_init_onboarding.py` (7/7); suite
1365 passed; E2E disposable-workspace completo.

---

## BLP-008 — Sincronización proyecto↔meta-brain (BUG-003)

**Defecto**: `sync_brain` y `reconcile_brain` escribían métricas sobre
`DOM:arqux` hardcodeado — cualquier proyecto distinto de ARQUX quedaba
invisible en el meta-brain, y reconcile abortaba con `E013_NOT_FOUND` si
el brain no tenía `OBJ` en `$3`.

**Fix** (`src/arqux/sync.py`):
- `_project_name()` — resuelve el nombre vía `IDN:project` del brain con
  fallback al directorio; `_normalize_dom_name()` (lowercase).
- `_upsert_meta_dom()` — crea `DOM:<proyecto>` si falta.
- Reconcile lista `$3/OBJ:*` y actualiza el primero; sin `OBJ` → registra
  en `errors[]` y continúa (`meta_synced=True`).

**Evidencia**: `tests/test_sync_reconcile.py` (5/5, incl. escenario de
reinicio de gobierno); suite 1370 passed; E2E vivo — `DOM:arqux` real
actualizado sin duplicados.

---

## BLP-009 — Higiene del core (find-workspace-root + BUG-004 residual)

**Defectos**: `_find_workspace_root` podía devolver un directorio
`.arqux` como workspace root (rutas `.arqux/.arqux/` en resolución de
identidad); `blueprint.ready` no impedía transicionar BLPs con
placeholders de plantilla sin llenar (BUG-004 P3); la máquina de estados
del ciclo de vida no estaba documentada (BUG-004 P4).

**Fixes**:

| Ítem | Cambio |
|---|---|
| Guarda de raíz | `identity_resolver._find_workspace_root`: `start=.arqux` → `parent`; candidatos `.arqux` skipped en walk-up |
| Gate de placeholders | `_pending_placeholders()` en `lifecycle.py` — markers descubiertos dinámicamente de `BLP_TEMPLATE.md` efectiva (workspace → paquete), regex con límites de palabra (sin falsos positivos en identificadores), §18 excluido (`☐`/`✅` son estado de compuerta). Rechazo: `OUT-ERROR code=VALIDATION pending=[...]` sin transición |
| Docs | `HANDLERS.md` §blueprint: tabla depurada + máquina de estados `draft → ready → in_progress → done` con handlers por transición |

**Compatibilidad**: tests que ejercen transiciones sobre BLPs
parcialmente llenos rellenan markers vía helpers (`_scrub_placeholders`,
`_fill_template_placeholders`); fixtures legacy/mínimos intactos.

**Evidencia**: `tests/test_blp009_guards.py` (7/7); suite 1377 passed.

---

## Resultado global

| Métrica | Valor |
|---|---|
| Suite | **1355 → 1377 passed**, 14 skipped, 0 regresiones |
| Issues cerrados | BUG-003, BUG-004, BUG-005, find-workspace-root, task-cycle-resolution → `verified` |
| Issues abiertos | BUG-003-cortex-dependency (upstream CODEC-CORTEX, escalado), issue-registry-sin-handlers (feature propuesto) |
| Auditoría | Heimdall: HD-11..18 resueltos (contradicción frontmatter↔§18, §13 como validaciones, exclusión de `☐` del gate); HD-17/18 documentados como limitaciones menores |

**Nota de proceso**: el servidor MCP en ejecución conserva módulos en
memoria — los fixes de `src/` se activan al reiniciar `arqux serve`.
El paquete instalado por `uv tool` ahora es editable apuntando a este
árbol, por lo que futuros cambios solo requieren reinicio del servidor.
