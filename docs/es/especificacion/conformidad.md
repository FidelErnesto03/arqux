---
doc_type: canon
status: normative
version: 1.0.0
verified: 2026-11-15
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../../docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="../../../docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Canon · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Conformidad código ↔ canon — matriz de revisión

**Propósito:** instrumento para dirigir la revisión de lo que el código
**hace hoy** (actual) contra lo que el canon `docs/es/especificacion/` **exige**
(real). Cada fila: componente · comportamiento actual con evidencia ·
exigencia del canon · brecha · verificación.

**Corpus vivo ya migrado** (G-8, 2026-11-15): brain GRADIENT-12,
meta-brain canon+REGISTRY, 4 archivos absorbidos eliminados.
Esta matriz cubre el **software** — lo que sigue emitiendo/leyendo
el modelo viejo.

---

## A. Estructura de secciones del brain

| Componente | Actual (evidencia) | Canon exige | Brecha |
|---|---|---|---|
| `constants.py` `BrainSection`/`BRAIN_SECTION_TITLES` | enum y mapa = GRADIENT-12 (`$0..$10`); `ALL_BRAIN_SECTIONS` conserva los 16 nombres para compat-lectura | GRADIENT-12 (`cerebro-canon.md` §2) | **resuelto** (CYCLE-16) |
| `learning/sections.py` | `_TITLE_FOR_SIGIL` + `section_for_sigil()` resuelven por título contra el doc vivo | — | **parcialmente conforme**: quedan fallbacks posicionales — `_ID_FOR_SIGIL` (fallback `BrainSection` cuando el doc carece del título), `section_title()` (:86-92), `plan.py` fallback `$7` |
| `brain_structure.py` (validador) | valida GRADIENT-12 por id↔título canónico | valida GRADIENT-12 + `ARQX:artifact` en `$1` | **resuelto** (CYCLE-16) — fixtures actualizados al layout de 11 secciones |
| `templates/brain.cortex` / `meta-brain.cortex` | templates GRADIENT-12 emitidos | template GRADIENT-12 | **resuelto** (CYCLE-16) |
| `formats.py` `brain_from_model` | emite GRADIENT-12 (`ARQX`+concurrencia en `$1`, secciones legacy como apéndices titulados solo si llevan contenido) | emiten canon | **resuelto** (CYCLE-16) |
| `skill.install` registro | `SKL` → sección `SKILLS` (→`KNOWLEDGE` fallback) por título | nunca posicional | **resuelto** — era `$6` (=OBJECTIVES canónico) |
| `loops.py` `loop_register` | `LOOP` → `LOOPS` por título, fallback `$9` | nunca posicional | **resuelto** — era `$14` legacy |
| `learning.record` | `LNG` → `LESSONS` por título, fallback `$8` + `section_title` | nunca posicional | **resuelto** — era `$8` bare |
| `project.py` instrucciones de seed | prompt enseña GRADIENT-12 al agente | canon | **resuelto** — enseñaba el layout de 15 secciones |

## B. Eventos (PULSE → timelog `$5 EVENTS`)

| Componente | Actual | Canon exige | Brecha |
|---|---|---|---|
| `pulse.py` `record_pulse`/`append_pulse_to_brain` | append `AUD` a timelog `$5 EVENTS` cuando hay `ses_ref`; fallback brain-PULSE por título (nunca `$7` posicional) | append a timelog de la sesión `$5 EVENTS` | **resuelto** (CYCLE-16) |
| ~14+ emisores (`record_pulse` callers: `handlers/skill.py`, `cycle.py`, `blueprint/*`, `issue.py`, `identity/switch.py`…) | escriben vía `record_pulse` — mismo sink, destino resuelto | escriben al timelog vía `ses_ref` | **resuelto** — los callers que pasan `ses_ref` aterrizan en timelog |
| `blueprint/_helpers._record_to_brain` | enrutado por `record_pulse` | unificado | **resuelto** — buscaba PULSE con `sec.id=="$7"` (colisión con ACTIVE_CONTEXT canónico) |
| `next_pulse_event_id` | `SESNNN-EXXXX` con `ses_ref`; `E-XXXX` global solo sin sesión (compat) | `SESNNN-EXXXX` por sesión | **resuelto** (CYCLE-16) |
| `timelog_store.py` | `$0..$5` + `append_event` + declaraciones `AUD`/`DEC`/`ERR` | `+ $5 EVENTS` | **resuelto** |
| `evidence.list` / dashboard / contadores de sesión | `read_pulse_from_brain` fusiona brain-PULSE legacy + timelog EVENTS | leen timelog(s) | **resuelto** (lector unificado) |
| T1: `PULSE_*`, `session.pulse.gc`, `LNG:pulse_sweep`, señal `pulse density` | auto-sweep fuera del write-path; `_prune_timelog_events` = no-op (timelog nunca podado); `sweep`/`compact` explícitos actúan solo sobre brain-PULSE legado | retirados — eventos nunca se podan | **resuelto** — retiro efectivo sobre el corpus canónico; la poda explícita queda como mantenimiento de residuo legado |
| `session.close` | cuenta `pulse_events` vía `read_pulse_from_brain` — lector unificado (timelog `$5 EVENTS` + brain-PULSE legado); el SES portable se escribe en `SESSIONS` por título | reporta eventos del timelog propio | **resuelto** — fuente unificada, descripciones T1 retiradas (CYCLE-16) |

## C. Artefactos eliminados — readers huérfanos

| Componente | Actual | Canon exige | Brecha |
|---|---|---|---|
| `_project.py` `find_project_root` | cascada: `contexts/exec-*.cortex` → **meta-brain `WRK:current.project_root`** → `context.cortex` (compat-lectura); `find_write_project_root` excluye ambos slots compartidos | fallback a meta-brain `$7` (`WRK:current.project_root`) | **resuelto** (G-9, CYCLE-16) |
| `session.context.set` / `session.context.get` | escribe exec-context + meta-brain `WRK:current`; lee exec-context → `context.cortex` (solo si es el slot elegido) → meta-brain | escribe/lee meta-brain `$7` | **resuelto** — `_write_context` sin slug ya no recrea `context.cortex` |
| `session.handoff` + consumidores bootstrap | escriben `HND:<to>` en brain `ACTIVE_CONTEXT` por título | `HND:<to>` en brain `$7`; claim = consume la entrada | **resuelto** — `handoffs/` no se recrea; los 5 `HND` migrados siguen siendo residuo huérfano |
| `session.bootstrap` | lee context via `context_get` (exec → meta-brain) | lee meta-brain | **resuelto** |
| `sync.py` → meta-brain | resuelve `ACTIVE_CONTEXT`/`FOCUS`/`KNOWLEDGE`/`REGISTRY` por título (`REGISTRY`→`PROJECTS`→`DOMAINS` legacy) | escribir por título | **resuelto** — era COLISIÓN ACTIVA CRÍTICA |
| consumidores de `agents.cortex` (`protocol.py` adopt/onboard/release/pause/resume, `project.py`, `workspace.py`) | escriben `IDN:*` en meta-brain `REGISTRY`; `write_projects_index` retirado de `init_workspace` | leen/escriben meta-brain `$10 REGISTRY` | **resuelto** |
| `cortex_out.py` `format_status` | cuenta `DOM` en meta-brain `REGISTRY` (fallback `PROJECTS`/`DOMAINS`) | lee meta-brain `$10` | **resuelto** |
| `learn-policies.cortex` loader (`core/learning/_common.py:29-34`) | `_resolve_policy_path` **ya prefiere proyecto** y cae al template empaquetado `src/arqux/templates/` — nunca al ws | una por proyecto | **resuelto** — documentar el fallback-al-template silencioso (política de paquete aplica si falta la del proyecto: decisión implícita a revisar) |

## D. Metadata ARQX (`$15`/`$19` → cabecera `$1`)

| Componente | Actual | Canon exige | Brecha |
|---|---|---|---|
| `migrator.migrate_file` | inyecta `ARQX:artifact` dentro de `IDENTITY` cuando existe; `$19` solo para artefactos sin identidad (tasks, cycles, manifest) | `$1` para cerebros/identidades | **resuelto** (CYCLE-16) |
| `brain_from_model` | `ARQX:artifact{...version,last_writer,updated}` en `$1 IDENTITY` — concurrencia plegada | `$1` | **resuelto** (CYCLE-16) |
| emisores `$19` restantes (`_add_arqux_meta_section` para manifest/projects/task/cycle, `_migrate.py` rescue, writer `$0.1`→`$19`) | out-of-band deliberado para artefactos sin `IDENTITY`; el writer preserva estructura existente | `$19` permitido fuera de cerebros | **conforme por diseño** — canon restringe `$1` a cerebros/identidades |
| `sessions.py` bump de versión | `crud_update` sobre `$1/ARQX:artifact` con fallback `ERR:concurrency` legacy | `$1` | **resuelto** |
| `read_arqux_metadata` | `_ARQUX_META_PRIORITY` prioriza `$1` sobre `$15`/`$19` por sigilo | — | **resuelto** |

## E. Escritura/identidad

| Componente | Actual | Canon exige | Brecha |
|---|---|---|---|
| `identity.switch` | registra `HND` en `ACTIVE_CONTEXT` + evento vía `record_pulse` | handoff-evento → timelog `$5`; sin PULSE | **resuelto** |
| `protocol.adopt`/`protocol.onboard`/`release` | escribe `IDN:*` en meta-brain `REGISTRY` | escribe meta-brain `$10 REGISTRY` | **resuelto** |
| `identity.record`/`identity.elevate` | `LNG`→`LESSONS` por título + nudge candidatos | sin cambio (ya conforme) | **resuelto** |

## F. Residuos verificados en corpus vivo

| Ítem | Evidencia | Acción |
|---|---|---|
| `LOOP:vamos-ah` no parseaba (E017) | nombre guionado off-grammar — renombrado `vamos_ah` + `phases` compactado; `add_entry` ahora sanitiza nombres a `[A-Za-z0-9_]` | corregir nombre + sanitizar en writer | **resuelto** |
| `SES:heimdall`/`SES:alfred` `status:"active"` | normalizados a `current` (CYCLE-16); writer actual no emite `status` | normalizar a `current` | **resuelto** |
| `$0` del brain SIN declaraciones | poblado con 13 contratos `SIGIL:*_contract` + `$0:format` (CYCLE-16); los `I001` restantes son ruido inherente del codec (el meta-brain los emite igual) | declarar los sigilos en glosario (G-4) | **resuelto** |
| `LNG:________*` placeholders **×183** | **resuelto** — renombrados derivando el nombre del cuerpo (aprobado Arquitecto, CYCLE-16). Eran residuo histórico, no bug activo: el writer (`_derive_lesson_name`, `handlers/cortex/learning.py:65-98`) ya hace `lstrip(" -\"")` antes de derivar. 212 `LNG` totales en `$8` |
| `LNG:session_*` boilerplate ×22 | **drenado** — lecciones-censo de `compact_session_pulse` (`pulse.py`, `lng_name=f"session_{ses}"`) eliminadas por decisión del Arquitecto (CYCLE-16). El generador sigue vivo para futuros compacts explícitos |
| `SES` count = **24** total | 24 en `$10` — squatter movido (CYCLE-16) | mover el squatter a `$10` (G-4) | **resuelto** |
| Drift off-canon: `DEC`/`LNG` en FOCUS, `SES` en KNOWLEDGE | 6 `LNG`→`$8`, 1 `SES`→`$10`, **6 `DEC`→`$2 AXIOMS`** (decisiones fundacionales pre-timelog — aprobado Arquitecto) | re-seccionar (G-4) | **resuelto** |
| `AUD:E_0001` huérfano en brain `$7` | escrito por writer posicional del MCP server antiguo; migrado al timelog `SES021` `$5 EVENTS` con attr `migrated_from` (CYCLE-16) | re-ubicar en timelog | **resuelto** |

## G. Protocolo de verificación por fila

Para cada fila tocada:

1. **Antes**: `grep` del comportamiento actual + test que lo fije si falta.
2. **Cambio**: implementar destino canon; compat-lectura por título, nunca por número.
3. **Después**: `cortex_verify` en artefacto afectado → `valid=true`; suite delta 0; evidencia `AUD` en timelog `$5` (post-G-3b) o brain hasta el reroute.
4. **Cierre de fila**: marcar ✓ con commit SHA.

## H. Orden de ejecución propuesto

```
G-9  (readers huérfanos)  ← crítico: hoy el fallback ya está roto
G-2  (constants/maps)     ← una sola fuente de verdad estructural
G-3  (validator/template/builders + metadata $1)
G-3b ($5 EVENTS + reroute emisores + retiro T1)
G-4  (drift residual del brain)
G-5  (motor de aprendizaje — spec aprendizaje.md §5)
G-7  (OBJ:_ post-restart)
```

Regla transversal del plan: **los writers nuevos solo emiten posiciones
canónicas; los readers resuelven por título y toleran las posiciones
legacy que queden** (`$15`/`$19`/PULSE-archivado).

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
