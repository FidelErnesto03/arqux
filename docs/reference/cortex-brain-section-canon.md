# Canon de Secciones — `brain.cortex` (Nivel 3 / BRAIN)

**Estado:** canon vigente (ALFRED · CYCLE-16 · 2026-11-15, rev. AXIOMS)
**Basado en:** `niveles-cortex-arqux.md` §5 + estado real de `.arqux/brain.cortex`
                 + directriz del Arquitecto: cada brain porta sus propios
                 axiomas de comportamiento (impuestos por el proyecto o
                 elevados por aprendizaje forzado)
**Alcance:** `brain.cortex` de proyecto y `meta-brain.cortex` de workspace.
Identidades (`<agent>.cortex`) y skills tienen canon propio (Nivel 1/2) —
este documento NO los gobierna.

---

## 1. Por qué existe este canon

Antes de este documento coexistían **tres layouts incompatibles**:

| Fuente | Layout | Estado |
|---|---|---|
| `niveles-cortex-arqux.md` §5 | $0–$12 (IDENTITY…ISSUES) | Diseño vigente |
| `constants.py` `BrainSection` + `BRAIN_SECTION_TITLES` | $0–$12 (METADATA…ISSUES, con KNOWLEDGE en $2, sin PULSE/SESSIONS/ACTIVE_CONTEXT) | **Obsoleto** — contradice el diseño y la realidad |
| `.arqux/brain.cortex` real | $1–$11 del diseño + `$18 LOOPS` + `$19 METADATA` fuera de secuencia | Deriva parcial |

Consecuencia medida: el validador `brain_structure` espera títulos que el
brain real no tiene (`$2` debería ser KNOWLEDGE y es FOCUS), y el motor de
aprendizaje (`core/learning/sections.py`) resolvía sigilos a títulos
canónicos que no existían en el brain (`CNST→AXIOMS`, `RSK→AXIOMS`).

**Enmienda AXIOMS (Arquitecto, 2026-11-15):** cada brain porta sus propios
axiomas de comportamiento — impuestos por exigencia del proyecto o
**elevados por aprendizaje forzado** — lo que hace a cada brain único en
condiciones y comportamiento. `AXIOMS` es sección canónica en `$2`, entre
IDENTITY (quién soy) y FOCUS (qué hago ahora): el contrato conductual se
lee antes que el estado operativo. Distinto de los axiomas de framework en
`AGENTS.md` (transversales, kernel) y de los de identidad (contrato del
agente): estos son la constitución *del proyecto*.

**Regla del canon:** la numeración `$N` es **secuencial y sin huecos** desde
`$0`. El título es la identidad semántica; el número es solo orden físico.
Los consumidores (aprendizaje, bootstrap, verify, render) resuelven por
**título**, nunca por número hardcodeado.

---

## 2. Layout canónico

| # | Sección | Título exacto | Sigilos | Oblig. | Consumidores |
|---|---|---|---|---|---|
| $0 | Glosario | `GLOSSARY` (sin título visible) | declaraciones `SIGIL:name{type,weight,focus,desc}`, `GTYP`, `GMIC`, `GCON` | Sí | parser, validator, writer |
| $1 | Identidad | `IDENTITY` | `IDN`, `ARQX` | Sí | bootstrap, `identity.*`, verify |
| $2 | Axiomas | `AXIOMS` | `AXM` | Sí | **todo agente en bootstrap** (contrato conductual del proyecto) |
| $3 | Foco | `FOCUS` | `FCS` | Sí | bootstrap dashboard, verify E024 |
| $4 | Objetivos | `OBJECTIVES` | `OBJ` | Sí | verify E024, cycle/blueprint |
| $5 | Sesiones | `SESSIONS` | `SES` | Opc. | `session.*`, timelog, learning |
| $6 | Handoffs | `HANDOFFS` | handoff entries | Opc. | `handoff.*`, protocol |
| $7 | Pulso | `PULSE` | `AUD`, `DEC` (append-only, **acotado**) | Sí | `cortex.pulse`, auditoría |
| $8 | Lecciones | `LESSONS` | `LNG` | Opc. | `identity.record`, consolidaciones (`cycle.close`, `pulse.*`) — **única superficie de lecciones** |
| $9 | Contexto activo | `ACTIVE_CONTEXT` | `WRK`, `CTX` | Sí | bootstrap (`WRK:current`), loops |
| $10 | Riesgos | `RISKS` | `RSK`, `LIM`, `CNST`, `PFL` | Opc. | verify, planning |
| $11 | Conocimiento | `KNOWLEDGE` | `KNW`, `REF`, `DEP`, `DESC` | Opc. | **learning engine**, `cortex.knowledge` |
| $12 | Concurrencia | `CONCURRENCY` | `ERR`, concurrency state | Sí | `cortex.checkpoint`, locks |
| $13 | Issues | `ISSUES` | issue entries | Opc. | `issue.*`, triage |
| $14 | Loops | `LOOPS` | `LOOP` | Opc. | `loop_*` handlers, bootstrap resume |
| $15 | Metadata | `ARQUX_METADATA` | `ARQX:artifact`, `SKL`, `DEC`, `ERR` (declaraciones de artefacto) | Sí | `project.status`, verify |

### Notas por sección

- **$0 GLOSSARY** — único contenido estructural. PROHIBIDO contener memoria
  operativa (E033). Aquí viven `format`, declaraciones de sigilos, tipos,
  micro-glossario y contratos `attrs-pos`.
- **$1 IDENTITY** — `IDN:governor` (obligatorio en brain de proyecto).
  Identidad del *agente/proyecto*, no del documento.
- **$2 AXIOMS** — axiomas de comportamiento **del proyecto**: reglas
  non-negotiable impuestas por el Arquitecto o elevadas por aprendizaje
  forzado (corrección repetida → `AXM`). Recomendado `survive:min` o
  `severity:blocking` para que la mutabilidad del brain no los degrade.
  Hacen único a cada brain — dos proyectos pueden tener conductas
  divergentes por diseño.
- **$3 FOCUS / $4 OBJECTIVES** — la regla Nivel 3 del codec exige ≥1 `FCS`
  y ≥1 `OBJ` con `status∈{current,blocked}` y campos `what`/`goal` no
  vacíos (E024/E034). `status:done` NO cuenta como activo.
- **$5 SESSIONS** — trabajo y trazabilidad detallada viven aquí (y en
  timelog), NO en PULSE.
- **$7 PULSE** — append-only y **acotado por diseño**: eventos de auditoría
  recientes, no bitácora completa. El brain no debe crecer sin límite —
  sesiones y timelog portan el detalle; PULSE porta el pulso + punteros.
- **$8 LESSONS** — **única superficie de lecciones del workspace**
  (regla del Arquitecto 2026-11-15): toda captura — `identity.record`
  (cualquier kind) o consolidación — escribe `LNG` aquí, con
  `type/cause/lesson/prevention/agent`. La elevación es gobernada y tiene
  dos destinos: `$11 KNW` (conocimiento operativo, `cortex.learn.elevate`)
  o `<agent>.cortex` `AXM`/`LIM` (conocimiento conductual,
  `identity.elevate`). `.lessons.cortex` y la sección `BEHAVIORAL LESSONS`
  de las identidades están deprecados como almacenes — la identidad solo
  porta contratos elevados.
- **$9 ACTIVE_CONTEXT** — `WRK:current` es la single source of truth del
  estado de trabajo del agente (bootstrap lo lee primero).
- **$14 LOOPS** — declaraciones `LOOP:<name>{state,index,phases,...}` de
  loops autónomos. El skill `autonomia` los gobierna.
- **$15 ARQUX_METADATA** — `ARQX:artifact{level,name,usage,kind,version}`
  + declaraciones `SKL:`/`DEC:`/`ERR:` de artefactos ArqUX. Equivale al
  "colofón" del documento. Título en una sola palabra con underscore:
  el regex del validador estructural solo acepta `[A-Z_]+`.

---

## 3. Reglas de orden y escritura

1. **Ordinal estricto** — las secciones se emiten en el orden de la tabla.
   `$N` sin huecos ni duplicados.
2. **Título canónico exacto** — mayúsculas, guion bajo en
   `ACTIVE_CONTEXT`/`ARQUX_METADATA` según tabla. El validador
   `brain_structure` compara contra esta tabla.
3. **Secciones opcionales ausentes** — está permitido omitir una sección
   opcional vacía; el validador emite warning (no error).
4. **Extensiones** — una sección nueva se añade como `$16+` con título
   propio y DEBE registrarse aquí antes de usarse en producción.
5. **Resolución por título** — todo consumidor nuevo DEBE resolver la
   sección por título (como hace `learning/sections.py`), nunca por
   número. El número puede renumerarse en migraciones; el título no.
6. **Crecimiento acotado** — el brain acumula axiomas, lecciones y
   **punteros**, no bitácoras. Trazabilidad detallada → SESSIONS/timelog.
   PULSE se rota/archiva; ningún agente debe leer ~700KB para bootstrap.

### 3.1 Ciclo de vida de PULSE (retención T1 — implementado)

Un `AUD` tiene vida útil **mientras es retomable**: puede cambiar una
decisión, alimentar un resume o documentar trabajo en curso. Cuando su
sesión cierra, su tarea termina o su issue se resuelve, el evento pasa de
contexto operativo a registro histórico — y el registro ya vive en
`$5 SESSIONS`, evidencias BLP y `.arqux/timelog/`.

**Ventana caliente (T1, `src/arqux/pulse.py`):**

| Parámetro | Valor | Regla |
|---|---|---|
| `PULSE_KEEP_COUNT` (K) | 20 | Solo los 20 `AUD` más recientes sobreviven por rango |
| `PULSE_KEEP_DAYS` (T) | 5 | Solo `AUD` con `age ≤ 5 días` sobreviven por edad |
| `PULSE_SWEEP_AT` | 40 | El write path dispara sweep automático al superarlo |

- **Regla**: un `AUD` se conserva solo si `rank ≤ K` **Y** `age ≤ T` —
  la ventana se cierra por el primer límite alcanzado (intersección).
- **Exenciones duras**: `kind:"session"` (anclas/índice de pulso) y la
  **cola viva** — todo lo posterior a la última ancla de sesión (la
  sesión abierta es retomable por definición).
- **Disparadores**: automático tras cada `append_pulse_to_brain` cuando
  `AUDs > PULSE_SWEEP_AT`; explícito vía `session.pulse.gc` (`dry_run` disponible).
- **Consolidación**: los podados se resumen en `LNG:pulse_sweep`
  (rodante, acumula `total_pruned`/`sweeps`/`last_batch`) — apuntador,
  no traza. `session.pulse.compact` sigue produciendo el LNG semántico
  por sesión; T1 es la red de seguridad para lo que quede fuera.
- **Señal**: `arqux doctor` reporta `pulse density` (warn si `AUDs > 2×PULSE_SWEEP_AT`).

**Evoluciones documentadas (no implementadas):**

- **T2 — Exención por estado de entidad**: antes de podar, consultar el
  estado del asunto (`issue.*`, `task.*`, BLP abierto). Equivalente a
  *log compaction por clave* de Kafka: el evento vive mientras su clave
  está abierta. Costo: lookup cruzado por candidato — acotar a los que
  cruzan la ventana.
- **T3 — Cold tier de auditoría**: exportar el lote a
  `.arqux/archive/pulse-YYYY-MM.cortex` antes de podar (equivalente al
  audit backend de K8s). Hoy `.bak` + timelog cubren la función
  informalmente; T3 la haría explícita y rotativa.

---

## 4. Mapa sigilo → sección (motor de aprendizaje)

El aprendizaje eleva entradas nativas a secciones canónicas por significado
de sigilo. Mapa vigente:

| Sigilo | Sección canónica | Título | Notas |
|---|---|---|---|
| `AXM` | $2 | AXIOMS | regla conductual del proyecto (mandato o aprendizaje forzado) |
| `SES` | $5 | SESSIONS | registros de sesión |
| `LNG` | $8 | LESSONS | lecciones (behavioral/process) |
| `KNW` | $11 | KNOWLEDGE | conocimiento durable |
| `CNST` | $10 | RISKS | restricciones/constreñimientos |
| `RSK` | $10 | RISKS | riesgos |
| `PFL` | $10 | RISKS | pitfalls |
| `LIM` | $10 | RISKS | límites |
| `STP` | $9 | ACTIVE_CONTEXT | próximos pasos = trabajo activo |
| `NXT` | $9 | ACTIVE_CONTEXT | cola de acciones |
| `WRK` | $9 | ACTIVE_CONTEXT | memoria de trabajo |
| `FCS`/`OBJ` | $3/$4 | FOCUS/OBJECTIVES | foco y objetivos |
| `IDN` | $1 | IDENTITY | identidad de agente/proyecto |
| `ARQX`/`SKL` | $15 | ARQUX_METADATA | metadata de artefacto |
| `LOOP` | $14 | LOOPS | loops autónomos |
| `AUD`/`DEC` | $7 | PULSE | eventos append-only (acotados) |

**Elevación forzada → AXIOMS:** cuando el aprendizaje detecta una
corrección repetida o una regla de comportamiento del proyecto, eleva a
`AXM` en `$2` (no a LESSONS) — las lecciones informan, los axiomas mandan.

---

## 5. Deuda de reconciliación (pendiente de ejecución)

| # | Ítem | Estado |
|---|---|---|
| R-1 | `constants.py`: `BrainSection` enum + `BRAIN_SECTION_TITLES` → canon $0–$15 con AXIOMS | **Hecho** (2026-11-15) |
| R-2 | `core/learning/sections.py`: `_TITLE_FOR_SIGIL`/`_ID_FOR_SIGIL` → mapa §4 (incl. `AXM`→AXIOMS) | **Hecho** |
| R-3 | `brain.cortex` real: renumerar completo a canon ($2 AXIOMS nuevo, $18→$14 LOOPS, $19→$15 METADATA al final) vía MCP, dry-run + verify | **Hecho** (2026-11-14) — migración física aplicada vía `cortex_write` gobernado (733KB excede transporte MCP inline; mismo handler, validado + atómico + backup `.bak`). `cortex_verify` post: valid=true, 17 secciones, 519 entradas. NOTA: el servidor MCP `arqux` de la sesión corría código pre-canon — requiere restart (editable install → recoge `src/`) |
| R-4 | `brain_structure.py` + `brain_semantics.py`: validar contra canon | **Hecho** — semantics resuelve vía `BrainSection`, tests actualizados |
| R-5 | `meta-brain.cortex`: aplicar mismo canon (estructura puede diferir — verificar) | Por verificar |
| R-6 | Writer: emitir secciones en orden canónico; `_lesson.py`/`_migrate.py` aún emiten `$19` → migrar a `$15` | **Hecho (parcial)** — `formats.py` (ambos builders) + `templates/brain.cortex` emiten $0–$15 con metadata al final; `_lesson.py` resuelve LESSONS por título; `_migrate.py` es path de reparación de artefactos no-brain (identidad) — fuera de scope |
| R-7 | Auditoría de referencias `$N` hardcodeadas (`session_identity` $4→$5 SESSIONS, `timelog_projection`, `handlers/*`) | **Hecho** — migrados: sessions/pulse/sync/loops/checkpoint/learning/cycle/level_policy/elevation/project.py/ref.py; restantes son artefactos no-brain (agents/identity/lessons/skills/meta-brain/projects) con canon propio; codec-genéricos preservan IDs del documento |
| R-8 | **Crecimiento del brain**: política de rotación/archivado de PULSE (hoy ~80% del archivo) + punteros a sesiones | **Hecho (ARQUX)** — 4 compactaciones de sesión (407 AUD) + 597 AUD huérfanos archivados en 4 `LNG:pulse_archive_*`; brain 733KB→274KB, PULSE 488KB→152KB (229 AUD = 33 anclas + cola viva SES021). Trazas íntegras en `$5 SESSIONS`/BLPs/timelog |
| R-9 | Sembrar `$2 AXIOMS` en `ARQUX/brain.cortex` con axiomas del proyecto (migración de AGENTS.md pertinentes + aprendizaje forzado) | **Hecho (semilla)** — `AXM:blp_project_path` + `AXM:blp_synthesize_first` (mandatos de `ARQUX/AGENTS.md` §2); contrato `AXM:axm` declarado en `$0`. Ampliable vía elevación del motor de aprendizaje |

---

## 6. Referencias

- `docs/architecture/niveles-cortex-arqux.md` §5 — niveles y regla E024/E034
- `src/arqux/constants.py` — `BrainSection`, `ALL_BRAIN_SECTIONS`, `BRAIN_SECTION_TITLES`
- `src/arqux/core/learning/sections.py` — resolución sigilo→sección
- `src/arqux/validators/brain_structure.py` — validador estructural
- `.arqux/skills/autonomia.skill.md` — loops (§14 del brain)
