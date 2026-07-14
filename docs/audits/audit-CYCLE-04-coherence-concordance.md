# OUT-AUDIT — Auditoría de Coherencia y Concordancia

**Proyecto:** ARQUX
**Ciclo:** CYCLE-04
**Alcance de Blueprint:** BLP-001 → BLP-014 (14 BLPs; BLP-015 excluido por "hasta la BLP-014")
**Fuentes auditadas:** `src/arqux/**`, `.arqux/skills/**`, `AGENTS.md`, `AGENTS.lite.md`, `AGENTS.full.md`, `HANDLERS.md`, tests asociados
**Agente:** Heimdall (watchdog, modo solo lectura)
**Fecha:** 2026-07-13
**Veredicto global:** ❌ **CYCLE-04 NO APROBADO** — 4/14 BLPs con defectos críticos de concordancia.

---

## 1. Metodología

Auditoría secuencial por franjas, contrastando:
- **Coherencia:** consistencia lógica interna (doc↔doc, blueprint↔blueprint, código↔código).
- **Concordancia:** acuerdo entre lo declarado (blueprints, skills, AGENTS.md) y la implementación real en `src/arqux/`.

Franjas:
- **A** — AGENTS.md* + `handler.list` + registro real de handlers (BLP-001/002/012)
- **B** — skills (workflows / mcp-handlers / protocol / cortex / ...) vs handlers (BLP-003/004)
- **C** — workflow docs w04..w12 vs handlers reales (BLP-006..011)
- **D** — BLP-005 (MCP/permisos/health), BLP-013 (pulse.compact), BLP-014 (CORTEX memory)

Verdad de referencia: `REGISTRY` en `src/arqux/handlers/__init__.py`, expuesto vía `handler.list(tier)` y MCP (`server.py:91`). Conteo real ejecutado en runtime = **91 handlers**.

---

## 2. Veredicto por BLP (secuencial)

| BLP | Tema | Concordancia | Severidad | Hallazgo clave |
|-----|------|--------------|-----------|----------------|
| 001 | adopción/proyecto | ⚠️ | ALTA | handler real = 91, doc 89; test de BLP-012 roto |
| 002 | capas AGENTS NANO/LITE/FULL | ❌ | ALTA | contradice BLP-012 sobre "declarar tabla de handlers" |
| 003 | skills→meta-handlers | ⚠️ | ALTA | `protocol.skill.md` §1 no adopta `session.bootstrap` |
| 004 | mcp-handlers.skill | ❌ | CRÍTICA | **skill objeto no existe en repo** |
| 005 | issues Heimdall MCP | ✅ | MEDIA | funciona, pero diagnóstico de permisos erróneo |
| 006 | w04 / `task.run` | ❌ | CRÍTICA | doc "6→1" falso: solo complete/fail, requiere task_id previo |
| 007 | w05 / `cortex.patch` | ❌ | CRÍTICA | doc "3→1" falso: solo `crud_update` |
| 008 | w06 / `protocol.onboard` | ✅ | BAJA | semánticamente correcto |
| 009 | w07 / `skill.install` | ❌ | CRÍTICA | doc "2→1" falso: no convierte ni escribe `.arqux/skills/` |
| 010 | w08 / `blueprint.synthesize` | ✅ | — | plena concordancia, 18 secciones verificadas |
| 011 | w10 / `session.handoff` | ❌ | ALTA | doc "4→1" falso: kwarg `to_agent` no existe (es `target_agent`), no fija contexto |
| 012 | `handler.list` | ❌ | CRÍTICA | off-by-one vivo: doc 89 vs REGISTRY 91; test falla |
| 013 | `pulse.compact` | ✅ | — | sólido, 18/18 tests verdes |
| 014 | CORTEX memory | ❌ | CRÍTICA | AC-03 roto por bug de ruta `session.py:637`; `done` prematuro |

**Resumen:** 6 ✅ (005, 008, 010, 013 + 2 con reservas), 8 ⚠️/❌. Críticos: 004, 006, 007, 009, 012, 014.

---

## 3. Hallazgos por franja

### FRANJA A — AGENTS.md* + handler.list + registro real (BLP-001 / 002 / 012)

**A-01 — CONCORDANCIA doc↔código — CRÍTICA**
- `AGENTS.md:18` → `TIE:full{... handlers:89 ...}`
- `src/arqux/handlers/__init__.py` (REGISTRY real) → **91 handlers** (`handler.list(FULL)` → `_total=91`).
- `handler.py:74-75` → `if tier_upper == "FULL": allowed = set(REGISTRY.keys())` → 91.
- Mismo fallo "off-by-one" que BLP-012 fue creado para eliminar (`BLP-012.md:40` "MCP registry real = 88... AGENTS.md declara 87"), pero persiste e **invertido** (doc=89, código=91, diferencia +2).

**A-02 — CONCORDANCIA tests↔código (guarda de regresión rota) — CRÍTICA**
- `tests/test_registry.py:17-18` y `:63-80`.
- `pytest tests/test_registry.py -q` → `FAILED test_handler_count_is_89 (assert 91 == 89)`; `FAILED test_module_handler_counts (cortex: expected 19, got 21)`.
- Los +2 extras en `cortex` son `cortex.checkpoint` y `cortex.compact` (BLP-014), añadidos sin actualizar `AGENTS.md` ni el test.
- BLP-012 AC-07 exige "Conteo de handlers por tier debe coincidir con registry (tests)" — **no se cumple** pese a BLP-012 marcado `done`.

**A-03 — COHERENCIA interna (BLP-002 vs BLP-012, ambos `done`) — ALTA**
- `BLP-002.md:213-214` → "AC-05: ... AGENTS.md §3: tabla de 7 handlers NANO ..." (exige declarar tabla explícita).
- `BLP-012.md:216` → "AC-04: AGENTS.md sin tabla. AC-05: AGENTS.lite.md sin $2 tabla. AC-06: AGENTS.full.md sin $2 tabla." (descubrimiento dinámico).
- Ambos blueprints cerrados como `done` con criterios **mutuamente contradictorios**.

**A-04 — COHERENCIA diseño↔código: "No hardcoded handler table" es falso para NANO/LITE — ALTA**
- `AGENTS.md:47`, `AGENTS.lite.md:25`, `AGENTS.full.md:28` vs `handler.py:17-57`.
- `handler.py:17-26` → `NANO_HANDLERS` (set de 8 literales); `handler.py:28-49` → `LITE_EXTRA` (set de 20 literales); sólo FULL es dinámico (`set(REGISTRY.keys())`).
- El "descubrimiento dinámico" es dinámico **solo para FULL**.

**A-05 — COHERENCIA interna del corpus doc (números de FULL se contradicen) — MEDIA**
- `AGENTS.full.md:13` → `AXM:delta_full{... Adds ~60 handlers ...}` (28+60 = **88**).
- `AGENTS.md:18` → `TIE:full{... handlers:89 ...}` (**89**).
- Dos números en el mismo corpus difieren en 1.

**A-06 — COHERENCIA interna de BLP-012 (número a verificar se autocontradice) — BAJA**
- `BLP-012.md:204` dice verificar **89**; su `evidence` (línea 24) y AC-03 (línea 216) dicen **88**. Tres números distintos (89 / 88 / 88).

**A-07 — COHERENCIA: código muerto `skill.sync` tras BLP-012 — MEDIA**
- `src/arqux/handlers/skill.py:720-1057`, `src/arqux/handlers/session.py:660`.
- `skill.sync` NO está registrado (grep `"name":"skill.sync"` → vacío; `handler.list` no lo devuelve) — BLP-012 AC-08 cumplido.
- Pero `sync_skill` y su doc interna permanecen como código muerto e invocado en `session.bootstrap` (línea 660 `"skill_sync": sync_result`). Riesgo de re-divergencia.

**A-08 — CONCORDANCIA: doc estático residual `HANDLERS.md` diverge 18 handlers — MEDIA**
- `HANDLERS.md:3` → "Total: 73 handlers" (24 governance + 49 utility). REGISTRY real = 91 → diverge 18.
- BLP-012 sólo eliminó `mcp-handlers.skill.md`; `HANDLERS.md` (raíz) re-diverge.

**Lista documentado vs real (Franja A)**

| Conjunto | Documentado | Real (REGISTRY) | Estado |
|----------|-------------|-----------------|--------|
| NANO | 8 (`AGENTS.md:16,46`; `handler.py:17-26`) | 8 | ✅ |
| LITE | 28 (`AGENTS.md:17`; `AGENTS.lite.md:13`) | 28 | ✅ |
| FULL | 89 (`AGENTS.md:18`) / ~88 (`AGENTS.full.md:13`) / 88 (`BLP-012.md`) | **91** | ❌ (+2) |

Los +2 reales = `cortex.checkpoint` y `cortex.compact` (BLP-014). No hay handlers huérfanos (todo handler real cae en FULL).

**Veredicto Franja A:** NO APROBADA. `handler.list` funciona para NANO(8)/LITE(28), pero la capa FULL está desincronizada y la guarda de regresión está rota.

---

### FRANJA B — Skills vs handlers (BLP-003 / 004)

**B-01 — CONCORDANCIA skill↔handler — CRÍTICA**
- `.arqux/skills/workflows/w10-identity-handoff.md:37, 61, 73, 96, 102` instruye `session.handoff(to_agent="Y")`.
- Handler real `src/arqux/handlers/session.py:781` → parámetro obligatorio es **`target_agent`** (no `to_agent`). El dispatch por nombre fallaría (kwarg desconocido).
- `w10:39` afirma que el meta-handler "agrupa read(origen)+read(destino)+context.set+evidence.record"; el handler real (`session.py:780-874`) solo lee brain vía `read_brain` y escribe `handoffs/<target>.cortex` + PULSE. No llama `context.set` ni `evidence.record`.

**B-02 — CONCORDANCIA skill↔handler — ALTA**
- `.arqux/skills/workflows/w04-reactive-task.md:11, 38-42, 54, 66-69`.
- Handler `src/arqux/handlers/task.py:436-472` (requiere `task_id` existente) y `task.py:511-524` (solo `complete_task`/`fail_task`).
- El skill afirma `task.run` reemplaza 6 llamadas (create+claim+execute+evidence+complete+lesson) con reducción 83%. En realidad el handler **no crea, no reclama, no registra lección**; requiere `task_id` ya existente. Reducción real ≈2→1, no 6→1.

**B-03 — CONCORDANCIA skill↔handler — ALTA**
- `workflows.skill.md:47` declara que el init de sesión "moved to protocol.skill.md §1. session.bootstrap handles it in 1 call".
- `protocol.skill.md:20-26` (§1 Session Start) **nunca menciona `session.bootstrap`**; documenta el flujo antiguo `handler.list(tier)` + `session.resume()` + dashboard manual.
- Meta-handler `session.bootstrap` existe (`session.py:1182`). Skill que debería usarlo no lo hace.

**B-04 — CONCORDANCIA skill↔handler — MEDIA**
- `.arqux/skills/workflows/w05-identity-evolution.md:27, 39, 45, 48`.
- Handler `cortex/patch.py:21-95` + firma `cortex/__init__.py:390-405` (parámetros **`path`, `content`**, no `deltas`).
- El skill pasa `deltas=(...)`; el handler espera `content`. Además afirma que consolida `cortex.entry.add + identity.record + evidence.record`; el handler solo parchea entradas vía `crud_update`.

**B-05 — CONCORDANCIA skill↔handler — MEDIA (menor)**
- `protocol.skill.md:68, 70` documenta `context.set(project,...)` / `context.get(path?)` sin prefijo `session.`. REGISTRY tiene `session.context.set` / `session.context.get`. Un agente que copie el nombre literal no encontraría el handler.

**B-06 — COHERENCIA interna (BLP-004) — CRÍTICA**
- `.arqux/skills/mcp-handlers.skill.md` **AUSENTE** en todo el repo (`find` recursivo no lo localiza; `ls .arqux/skills/` lista solo 6 skills).
- El objeto de BLP-004 ("consolidar mcp-handlers.skill.md, reparar estructura híbrida, restaurar secciones conceptuales") **no existe**. No puede "consolidarse/restaurarse" algo ausente.

**B-07 — COHERENCIA interna (BLP-004) — MEDIA**
- `protocol.skill.md:20` afirma que `handler.list` "reemplaza el viejo static mcp-handlers.skill.md".
- `skill.py:982` y `docs/arch_vision/handlers-catalogo.hcortex.md:10,725,833` lo siguen tratando como fuente de verdad de firmas (§6, 73 handlers, `registry_hash`).
- El generador real usa **§8** para el catálogo (no §6). Tres fuentes en conflicto sobre si el archivo debe existir.

**B-08 — COHERENCIA interna (BLP-004) — MEDIA**
- `src/arqux/handlers/skill.py:886-972` (fallbacks hardcodeados `_GLOSSARY_FALLBACK`, `_ARCHITECTURE_FALLBACK`, ...). Las secciones conceptuales que BLP-004 quiere "restaurar" solo existen como strings en código, no como skill curado.

**B-09 — COHERENCIA interna — BAJA**
- `cortex.skill.md:203, 207` etiqueta `HDL:sync_brain` como handler; es un helper de `src/arqux/sync.py`, **no** un handler registrado. Etiquetado impreciso.

**Concordancia general (Franja B):** Los 7 meta-handlers declarados existen con firmas verificables (`session.bootstrap` session.py:1182, `task.run` task.py:600, `blueprint.synthesize` blueprint/__init__.py:132, `protocol.onboard` protocol.py:161, `skill.install` skill.py:1078, `cortex.patch` cortex/__init__.py:390, `session.handoff` session.py:1183). Cruce automatizado de 91 handlers REGISTRY vs tokens en `.arqux/skills/` confirma **ningún handler inexistente referenciado** (los no coincidentes son rutas/archivos/CLI). Única divergencia de nombre: B-05.

**Veredicto Franja B:**
- **BLP-003 — AVANZADO PERO DEFECTUOSO:** el índice y la mayoría de workflows ya citan los meta-handlers (problema original resuelto a nivel de cita), pero persisten defectos de precisión que rompen el happy-path (D-B01 `session.handoff` kwarg erróneo CRÍTICO; D-B02 `task.run` alcance sobreestimado ALTA; D-B03 `protocol.skill.md` no adopta `session.bootstrap` ALTA).
- **BLP-004 — BLOQUEADO / INCONCLUSO:** el skill objeto no existe (CRÍTICO), hay contradicción documental sobre si debe existir, y sus secciones conceptuales solo viven como fallbacks en código. Requiere resolver la contradicción de diseño (¿fuente de verdad = `handler.list` runtime, o skill estático auto-sincronizado?) y luego regenerar/curar.

---

### FRANJA C — Workflow docs vs handlers reales (BLP-006 → 011)

**BLP-006 · w04-reactive-task.md · `task.run` — ❌ CRÍTICA**
- `task.py:436` (`run_task`), `task.py:511-524`: el handler **solo** marca complete/fail de una tarea **ya existente**; **no** ejecuta create, claim, update, evidence.record ni identity.record.
- `w04-reactive-task.md:11,54,66` afirma "create + claim + update + evidence + complete + identity.record (6→1, 83%)". Falso.
- `task.py:478-484` (`_load_task` → NOT_FOUND si no existe): el doc (`:37,:65`) muestra `task.run(obj, content=TK:task{...}, lessons=[LNG])` creando la tarea — **no soportado**.
- PUML vs texto: coinciden en describir el flujo falso (BAJA).

**BLP-007 · w05-identity-evolution.md · `cortex.patch` — ❌ CRÍTICA**
- `cortex/patch.py:21-95` (`patch_handler`): solo `crud_update` (reemplazo de cuerpo por selector, `:70-82`); **no** invoca `cortex.entry.add`, `identity.record` ni `evidence.record`.
- `w05-identity-evolution.md:11,13,39` declara "cortex.entry.add + identity.record + evidence.record (3→1, 67%)". Ninguna se ejecuta.
- Contradicción interna texto vs PUML (MEDIA): `:13,:39` (texto: 3 llamadas) vs `:29` (PUML: "ADD entry + UPDATE entry" = 2 mutaciones). Además el handler **no añade** entries (solo reemplaza), así que "ADD entry" del PUML también es falso.

**BLP-008 · w06-agent-adoption.md · `protocol.onboard` — ✅ BAJA**
- `protocol.py:126-151` (`onboard`): lee identidad (`:139-142`, lectura directa del `.cortex`) + `adopt` (`:144`) en 1 llamada. Coincide con "cortex.read + protocol.adopt (2→1)".
- Desviación menor (BAJA): el doc dice que lee vía `cortex.read` (mode=native); el código lee el archivo directamente. Efecto semántico idéntico. Aceptable.

**BLP-009 · w07-skill-lifecycle.md · `skill.install` — ❌ CRÍTICA**
- `skill.py:562-716` (`install_skill`): 3 pasos internos — **import** (raw a `originals/`, `:606-624`), **validate** (`$0` header, `:626-638`), **register** (append `SKL` a `brain.cortex`, `:640-687`). **No** llama `skill.convert` ni escribe CORTEX a `.arqux/skills/`.
- `w07-skill-lifecycle.md:10,27,29,42,52` afirma "skill.import + skill.convert (2→1, 50%)" y el PUML (`:29`) "Convierte a CORTEX y escribe" a `.arqux/skills/`. El handler NO convierte ni escribe a `.arqux/skills/` (escribe raw a `originals/` y registra SKL en `brain.cortex`).
- PUML desincronizado (ALTA): "Agrupa import + convert" / "Convierte a CORTEX y escribe" — falso.

**BLP-010 · w08-blueprint-lifecycle.md · `blueprint.synthesize` — ✅**
- `blueprint/synthesize.py:33-136`: escribe secciones en 1 llamada (`:114-122`), crea BLP si no existe (status=draft, `:108-109,:274`), valida contra `BLP_TEMPLATE.md` (`:80-99`), escritura atómica (`:122`).
- `templates/BLP_TEMPLATE.md` tiene exactamente §1–§18 (18 markers). Afirmación del doc (`:20,:91`) correcta.
- Handlers de fase referenciados existen; `synthesize` no cambia status (doc `:111` lo reconoce).

**BLP-011 · w10-identity-handoff.md · `session.handoff` — ❌ ALTA**
- `session.py:780-874` (`handoff`): lee sesión actual (`read_brain`, `:822-827`), serializa a CORTEX, escribe `.arqux/handoffs/<target>.cortex` (`:850-853`) y un PULSE (`:855-865`). **No** lee identidad destino, **no** llama `session.context.set`, **no** llama `evidence.record`.
- `w10-identity-handoff.md:12,18,39` declara "read(origen) + read(destino) + context.set + evidence.record (4→1, 75%)". Solo el "read origen" (parcial) ocurre.
- PUML vs realidad (MEDIA): `:41` ("Fija contexto (project, scope)") — el handler **no** fija contexto activo ni actualiza el header. La promesa "header se actualiza automáticamente" (`:61,:74`) no se cumple.

**Observación transversal — etiquetas BLP en docstrings de handlers (MEDIA)**
Los docstrings citan BLPs distintos a la regeneración auditorada:

| Handler | Comenta en código | BLP esperado |
|---------|-------------------|--------------|
| `task.run` | "BLP-010" (`task.py:432,446,600`) | BLP-006 |
| `cortex.patch` | "BLP-010" (`cortex/patch.py:1`) | BLP-007 |
| `protocol.onboard` | "BLP-003" (`protocol.py:132,161`) | BLP-008 |
| `skill.install` | "BLP-010" (`skill.py:558`) | BLP-009 |
| `blueprint.synthesize` | "BLP-007" (`synthesize.py:1`, `blueprint/__init__.py:132`) | BLP-010 |
| `session.handoff` | "BLP-010" (`session.py:776,790,1183`) | BLP-011 |

**Veredicto Franja C:** REPROBADA (3/6 concordancias reales). ✅ Logradas: BLP-008, BLP-010. ❌ Fallidas: BLP-006, BLP-007, BLP-009, BLP-011.
**Patrón dominante:** los 4 docs fallidos describen meta-handlers que "consolidan N llamadas atómicas", pero las implementaciones **no envuelven esas llamadas atómicas** — solo hacen una fracción. Las reducciones 83%/67%/50%/75% son infladas y no verificables contra el código.

---

### FRANJA D — BLP-005 / 013 / 014

#### BLP-005 — Issues operacionales Heimdall (status: `done`)
**Concordancia: CONCORDANTE CON RESERVAS (discrepancias de documentación, no funcionales).**

| # | Afirmación | Verificación | Resultado |
|---|-----------|--------------|-----------|
| 1 | `protocol.onboard` registrado y expuesto como MCP tool | `handlers/protocol.py:161`; `server.py:91-103` registra TODO el REGISTRY | ✅ |
| 2 | `ARQUX_AGENT_ROLE` configurado → mutations permitidas | `permissions.py:179` (default `ROLE_GOVERNOR`); `permissions.py:228` (no-strict + governor → bypass) | ⚠️ funciona, diagnóstico erróneo |
| 3 | Health check `.arqux/` structure FAIL resuelto | `doctor.py:140-170` (`check_bak_files`) → PASS; `doctor.py:265-283` (`check_arqux_dir_structure`) devuelve **`warn`**, nunca `fail` | ⚠️ el "FAIL" real era de `.bak` |

- **[MEDIA] Diagnóstico de permisos contradictorio con el código.** BLP-005 §1 (línea 36) y T-1.1 (línea 192) afirman: *"ARQUX_AGENT_ROLE no está en environment → MCP server asume rol auditor, bloqueando toda mutación"*. `permissions.py:179` y `:228` demuestran que si `ARQUX_AGENT_ROLE` está **vacío**, el rol default es **GOVERNOR** (no auditor) y en modo no-estricto GOVERNOR salta todas las comprobaciones. El "auditor read-only" solo ocurre si el rol se fija explícitamente a `auditor`.
- **[MEDIA] Remediación de `.bak` imprecisa.** Evidence (línea 24) dice *".bak files movidos a backups/"*. En realidad `doctor.py:291-312` (`fix_bak_files`) hace `git rm` + añade `*.bak` a `.gitignore` — **no los mueve**. Siguen en disco: `.arqux/brain.cortex.bak`, `.arqux/cycles/CYCLE-02/cycle.cortex.bak`, `.arqux/backups/brain.cortex.bak`. El doctor PASÓ solo porque ya no están trackados en git.
- **[BAJA] "structure FAIL" es nombre incorrecto.** El check `.arqux/ structure` (`doctor.py:265`) devuelve `warn` (hoy falta `identities/` y `templates/`), no `fail`. El FAIL original provenía de `check_bak_files`, un check distinto.
- **[MEDIA] AC-06 "health check sin FAIL" no se cumple.** El doctor reporta **1 FAIL**: `README badge: Badge shows 73, actual is 92` (`doctor.py:215-257`). Fuera del alcance de los 3 issues, pero contradice la aceptación blanket del BLP.

**Veredicto BLP-005:** Las 3 incidencias operativas están funcionalmente resueltas. Las discrepancias son de precisión documental/diagnóstico, no de implementación.

#### BLP-013 — pulse.compact (status: `done`)
**Concordancia: ✅ TOTAL.**

| Reclamo | Evidencia |
|---------|-----------|
| `compact_session_pulse()` en `pulse.py` | `pulse.py:173-354` (lee PULSE, filtra por sesión, sintetiza LNG, poda) |
| `_prune_pulse_entries()` | `pulse.py:357-393` |
| LNG en §7 | `crud_add(brain_path, "$7", "LNG", ...)` `pulse.py:324-325` |
| SES nunca podadas | `pulse.py:252` (`session_events` excluye `kind=="session"`) |
| Idempotente | `pulse.py:206-217` |
| `dry_run` | `pulse.py:311-321` |
| Meta-evento AUD | `append_pulse_to_brain(kind="pulse_compact")` `pulse.py:333-342` |
| `session.close` integra compact | `session.py:98-105` |
| `pulse.compact` handler MCP | `session.py:1184` (REGISTRY=True) |

- Tests: `tests/test_pulse_compact.py` = 18 tests, **todos pasan**.

**Veredicto BLP-013:** Implementación fiel a lo declarado. Concordancia total.

#### BLP-014 — CORTEX-native working memory (status: `done`, usuario indica `in_progress`)
**Concordancia: ❌ DISCORDANTE — defecto CRÍTICO de persistencia.**

**Lo que SÍ concuerda:**
- `checkpoint_context()` — `session.py:882-984`.
- `session.bootstrap` carga `WRK:current` (`wrf_current`) — `session.py:633-645`.
- `compact_context()` (AX:compact / WRK:full) — `session.py:1008-1095`.
- `cortex.checkpoint` y `cortex.compact` registrados como MCP — `session.py:1185-1186`.
- `AGENTS.md` actualizado con `WRK` (línea 10), `AXM:memory_format` (32), `AXM:compact` (33), `WK:cortex_memory` (34).

**Discrepancias:**
- **[CRÍTICA/ALTA] AC-03 "WRK:current sobrevive entre turnos" FALLA.** Bug reproducible en `tests/test_cortex_memory.py:97-130` → **1 failed, 24 passed**. Causa: `bootstrap` pasa `arqux_root.parent` (dir del proyecto, p.ej. `pd`) a `_read_wrk_current` en `session.py:637`, pero `_read_wrk_current` hace `root / BRAIN_CORTEX` asumiendo que `root` es el dir `.arqux` (`session.py:475`). Como `find_project_root` devuelve el `.arqux` (`core/state/_project.py:160`), `arqux_root.parent` = `pd`, busca `pd/brain.cortex` (inexistente) → `None` → bootstrap cae a default `idle`. El checkpoint SÍ escribe en `pd/.arqux/brain.cortex` (`$5/WRK:current`, confirmado por `crud_read`), pero el bootstrap lo lee de ruta equivocada. Tras `checkpoint` + `bootstrap`, el estado vuelve a `idle`. **El ciclo bootstrap→checkpoint→bootstrap no redondea.**
- **[ALTA] El status `done` es falso frente a su propia checklist.** T-7 (tests) marcado `[~]` (línea 228) — el test de persistencia falla. T-8 marcado `[ ]` (línea 229). La evidencia admite "6/7 tests pasan" — el 1 fallido es AC-03. El estado real es `in_progress` (como indica el usuario), más preciso que el `done` del archivo.
- **[MEDIA] Desajuste de sección $5 vs $8.** El template de `brain.cortex` crea `WRK:current` en **$8** (`formats.py:683`, `ACTIVE_CONTEXT`), pero BLP-014 escribe/lee en **$5** (`session.py:404-405`). Tras un checkpoint hay DOS `WRK:current` en el brain — `crud_read("WRK:current")` devuelve 2 entradas. Riesgo de ambigüedad adicional.

**Veredicto BLP-014:** Handlers existen y están expuestos, `AGENTS.md` al día, pero la **aceptación central (persistencia entre turnos) está rota por bug de ruta en `session.py:637`**. `status: done` no se sostiene. Fix sugerido (no aplicado): pasar `arqux_root` en vez de `arqux_root.parent` a `_read_wrk_current` en `session.py:637`.

**Veredicto Franja D:** ~80% implementada y funcional. BLP-013 ejemplar. BLP-005 cumple en lo operativo pero su narrativa de causa-raíz es imprecisa. BLP-014 es la anomalía real: su promesa central (memoria que sobrevive entre turnos) no funciona hoy, y está marcado `done` incorrectamente.

---

## 4. Hallazgos transversales (CRÍTICOS)

- **A-01** `AGENTS.md:18` dice 89 handlers; `REGISTRY` real = **91**. El bug que BLP-012 fue creado para exterminar **sigue vivo e invertido**.
- **A-02** `tests/test_registry.py` falla (`91≠89`, `cortex 21≠19`) — guarda de regresión rota pese a BLP-012 `done`.
- **B-06** `mcp-handlers.skill.md` **no existe** en el repo; BLP-004 declara consolidarlo sobre algo ausente.
- **BLP-014** `session.py:637` pasa `arqux_root.parent` a `_read_wrk_current` que espera el dir `.arqux` → checkpoint no sobrevive a bootstrap. AC-03 falla (`test_cortex_memory.py:97-130`).
- **A-04** "No hardcoded handler table" es falso para NANO/LITE (hardcodeados en `handler.py:17-57`); solo FULL es dinámico.

---

## 5. Patrón de falla dominante

Los 4 BLPs fallidos (006/007/009/011) describen meta-handlers que "consolidan N llamadas atómicas (create/claim/identity.record/evidence.record/skill.convert/context.set)", pero las implementaciones **no envuelven esas llamadas atómicas** — solo hacen una fracción del trabajo (complete/fail, crud_update, import+register, read+write archivo). Los handlers sí existen y son funcionales, pero su superficie real es sustancialmente menor a la prometida por los docs. Las reducciones 83%/67%/50%/75% **no son verificables contra el código actual**.

---

## 6. Recomendaciones de endurecimiento (AX:hardening_intelligence)

1. **Des-bloquear BLP-004:** decidir fuente de verdad (¿`handler.list` runtime o skill estático auto-sincronizado?) y regenerar/curar `mcp-handlers.skill.md` antes de cerrar CYCLE-04.
2. **Reconciliar doc↔código en 006/007/009/011:** o corregir los docs a la superficie real de los handlers, o implementar el wrapping atómico prometido. Las métricas "N→1" publicadas deben ser verificables.
3. **Fix BLP-014:** en `session.py:637` pasar `arqux_root` (no `.parent`) a `_read_wrk_current`; revertir estado a `in_progress` y cerrar T-7/T-8.
4. **Sincronizar conteo:** `AGENTS.md:18`→91, `AGENTS.full.md:13`→~63; corregir `test_registry.py` (count 91, cortex 21).
5. **Resolver colisión BLP-002 vs BLP-012** sobre "declarar tabla de handlers" en la documentación de arquitectura.
6. **Limpiar código muerto** `sync_skill` (`skill.py:720-1057`) y decidir estatus de `HANDLERS.md` (re-diverge 18 handlers).
7. **Precisión documental BLP-005:** corregir el diagnóstico de permisos (`permissions.py:179` → default GOVERNOR, no auditor) y la remediación de `.bak` (git-ignore, no mover).
8. **Re-etiquetar docstrings** de handlers con la numeración BLP correcta (tabla en Franja C) para evitar desincronización futura.

---

*Fin del informe. Generado por Heimdall (modo solo lectura). No se mutó estado de gobernanza.*
