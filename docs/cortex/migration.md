# Deuda de reconciliación y migración — GRADIENT-12

**Estado:** migración de datos **ejecutada**; deuda de **código**
pendiente (ALFRED · CYCLE-16 · 2026-11-15).
**Carpeta:** `docs/cortex/`.

---

## 1. Estado ejecutado — G-8 consolidación (2026-11-15)

### 1.1 brain.cortex → GRADIENT-12 ✓

`ARQUX/.arqux/brain.cortex` reescrito al canon: `$1 IDENTITY` (con
`ARQX:artifact{version,revision,last_writer}` en cabecera — `ERR:concurrency`
fundido), `$2 AXIOMS`, `$3 KNOWLEDGE`, `$4 RISKS`, `$5 FOCUS`,
`$6 OBJECTIVES`, `$7 ACTIVE_CONTEXT`, `$8 LESSONS`, `$9 LOOPS`,
`$10 SESSIONS`. **283 entradas al momento de la migración (+N por
escrituras posteriores), `cortex_verify` valid=true**. Diagnósticos
de la época, todos cerrados en CYCLE-16: `LOOP:vamos-ah` E017 →
renombrado `vamos_ah`; 2 `SES status:"active"` → `current`; **183
`LNG:________*` placeholders → renombrados derivando el nombre del
cuerpo** (decisión Arquitecto; el writer ya hacía `lstrip(" -\"")`
— residuo pre-fix, no bug activo); 22 `LNG:session_*` boilerplate →
**drenados**; 6 `LNG` en FOCUS → `$8`; 6 `DEC` pre-timelog
(2026-10-10) → `$2 AXIOMS` (decisión Arquitecto — semánticamente
axiomas fundacionales); `AUD:E_0001` huérfano en `$7` → timelog
`SES021` `$5 EVENTS` con `migrated_from`; **`$0` poblado** con 13
contratos `SIGIL:*` + `$0:format`. Los `I001` restantes son ruido
inherente del codec (el meta-brain los emite igual).
Eliminadas: HANDOFFS, ISSUES, CONCURRENCY (→`$1`), PULSE →
`archive/hygiene-2026-11-15/pulse-legacy.cortex` (**276 AUD**
preservados — conteo directo). Backup: `brain.cortex.pre-gradient12`
en archive.

### 1.2 meta-brain.cortex → canon + REGISTRY ✓

Layout canónico `$1..$10`: IDENTITY + AXIOMS + KNOWLEDGE + RISKS +
FOCUS + OBJECTIVES (`OBJ:workspace` sembrado) + ACTIVE_CONTEXT +
LESSONS + LOOPS + **REGISTRY** (PROJECTS + AGENTS unificados).
**31 entradas de datos** (38 líneas sigilo incl. las 7 declaraciones
del `$0`), valid=true.

### 1.3 Merges ejecutados (artefactos eliminados)

| Eliminado | Absorbido por |
|---|---|
| `ws/.arqux/agents.cortex` | meta-brain `$10 REGISTRY` |
| `ws/.arqux/projects.cortex` | meta-brain `$10 REGISTRY` |
| `ws/.arqux/context.cortex` | meta-brain `$7 ACTIVE_CONTEXT` (`WRK:current`) |
| `ws/.arqux/learn-policies.cortex` | una por proyecto (decisión Arquitecto) |

### 1.4 Archivados (→ `archive/hygiene-2026-11-15/`)

~89 `*.issue.md` legados + ~23 `*.pre-migracion`/sidecars relevantes +
`*.bak.1` + `pulse-legacy.cortex` (276 AUD). Eliminados dirs vacíos:
`loops/`, `packages/` (proyecto + ws). `$19 ARQUX METADATA` fundido
a `$1` en: 5 handoffs, `learn-policies.cortex`, 2 issues `.cortex`
(una fusión dejó attrs sin coma — reparado 2026-11-15).

**Advertencia (revisada CYCLE-16)**: `$19` quedó como slot
**out-of-band deliberado** para artefactos sin `IDENTITY` (tasks,
cycles, manifest, rescue `_migrate.py`, normalización `$0.1`→`$19`
del writer). Los artefactos con sección `IDENTITY` reciben
`ARQX:artifact` en `$1` — `migrator.migrate_file` y `brain_from_model`
ya emiten ahí, y los templates canónicos nacen conformes.

**G-8b (misma operación)**: `handoffs/*.cortex` eliminados — el
artefacto era redundante (payload = estado pendiente). Los 5 payloads
migraron a `HND:<to>` en brain `$7 ACTIVE_CONTEXT` vía
`cortex_entry_add`; `handoff-canon.md` eliminado. **Residuo cerrado
(CYCLE-16)**: `session.handoff` ya escribe `HND:<to>` por título y
`handoffs/` no se recrea — los `HND` migrados drenan al claimear.
También archivados: `manifest.md`, `meta-brain.md`, `projects.md`
(narrativa/template de init), 2 `issues/*.md` legados,
`.sessions.lock` huérfano eliminado.

## 2. Deuda restante — código

| # | Ítem | Estado |
|---|---|---|
| G-4 | Drift off-canon **cerrado**: 6 LNG→`$8`, 1 SES→`$10`, 6 `DEC`→`$2 AXIOMS` (aprobado Arquitecto — axiomas fundacionales), 183 `LNG:________*`→nombres derivados del cuerpo (aprobado), 22 `LNG:session_*` drenados (aprobado), `AUD:E_0001`→timelog `SES021` `$5 EVENTS` con `migrated_from` | **Hecho** (CYCLE-16) |
| G-5 | Dinámica del motor (clustering temático, señal-densidad, dedup, drenaje `$8`) | Spec lista en `learning.md` §5 — pendiente aprobación final |
| G-7 | `OBJ:_` en OBJECTIVES — eliminado (delete `$6/OBJ:*` + re-add `OBJ:sync`); el selector `_` está vedado por T-022, la ruta fue wildcard+restaurar | **Hecho** |
| B-rem | `next_pulse_event_id` → `SESNNN-EXXXX` con `ses_ref` (compat `E-XXXX` sin él); auto-sweep fuera del write-path; pruner de timelog = no-op (eventos nunca podados); `sweep`/`compact` explícitos quedan para residuo brain-PULSE legado | **Hecho** |
| N-gram | Nombres de entrada off-grammar (`-`) — codec estricto los rechaza (E017, ej. `LOOP:vamos-ah` → renombrado `vamos_ah`). `add_entry` ya sanitiza a `[A-Za-z0-9_]` + `_entry_matches` normaliza el selector (write/read simétrico). Residual: archivos con nombres guionados preexistentes quedan alcanzables por la normalización de lookup | **Hecho** |
| T-leak | Tests sin `path`/`chdir` fugaban escrituras al workspace real (`IDN:new-agent` en meta-brain, `agents.cortex` recreado) | **Hecho** — `test_protocol` ahora pasa `path`; `agents.cortex` archivado |

### Deuda de código cerrada (CYCLE-16)

| # | Ítem | Estado |
|---|---|---|
| G-2 | `BrainSection`/`BRAIN_SECTION_TITLES` = GRADIENT-12; `ALL_BRAIN_SECTIONS` queda para compat-lectura | **Hecho** |
| G-3 | `brain_structure` valida GRADIENT-12; templates canónicos; `brain_from_model`/`migrator` emiten `$1` | **Hecho** |
| G-3b | `$5 EVENTS` en timelog + reroute `pulse.py`/emisores por título | **Hecho** (IDs por sesión y retiro T1 → B-rem) |
| G-9 | `find_project_root` cae a meta-brain `WRK:current`; `context.cortex` no se recrea; `agents`/`projects` en REGISTRY | **Hecho** |
| W-pos | Writers posicionales retirados: `sync.py`→meta-brain, `sessions.py`, `checkpoint`, `loops`($14→LOOPS), `learning`($8→LESSONS), `skill.install`($6→SKILLS), `blueprint._record_to_brain`($7→record_pulse), `format_status`(projects.cortex→REGISTRY) | **Hecho** — suite 2920/0 |

### Deuda histórica cerrada (CYCLE-16)

| # | Ítem | Estado |
|---|---|---|
| R-1..R-9 | Canon $0–$15 inicial, AXIOMS sembrado, PULSE T1, `$0.1`→`$15`/`$19`, resolución por título | Hecho |
| G-1 | Renumeración física brain → GRADIENT-12 | **Hecho 2026-11-15** |
| G-6 | meta-brain → canon + REGISTRY | **Hecho 2026-11-15** |
| G-8 | Consolidación de artefactos (merges, archive, dirs vacíos, `$19`→`$1`, handoffs→`$7`) | **Hecho 2026-11-15** |
