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

# `docs/es/especificacion/` — el dominio `.cortex` del framework ArqUX

Todo lo que un `.cortex` ES, dónde vive cada artefacto, cómo se compone
el brain y cómo aprende el sistema. Documentos separados por la
**pregunta** que responden.

> **Autoridad normativa:** este corpus ES **es el corpus de origen** — los
> documentos se redactaron nativamente en español; no existe un espejo
> normativo en inglés. En cualquier divergencia futura entre traducciones,
> gana este corpus. Los artefactos `.cortex` citados (sigils, entradas,
> ejemplos) permanecen literales: el formato en sí no se traduce.

## Mapa de lectura por pregunta

| Pregunta | Documento |
|---|---|
| ¿Qué es un `.cortex`? ¿Qué reglas físicas aplican a todos? | `formato.md` |
| ¿Qué artefactos existen y dónde vive cada uno? | `artefactos.md` |
| ¿Cómo está organizado el brain? ¿Dónde va este dato? | `cerebro-canon.md` |
| ¿Y el meta-brain del workspace? | `meta-cerebro-canon.md` |
| ¿Y el contrato de una identidad/agente? | `identidad-canon.md` |
| ¿Y el timelog de una sesión? | `timelog-canon.md` |
| ¿Y un skill (nivel 2)? | `habilidad-canon.md` |
| ¿Y learn-policies? ¿Y dónde viven los registros? | `registro-canon.md` |
| ¿Y ciclos, BLPs, tareas, issues? | `gobernanza-canon.md` |
| ¿Y audits, archive, backups, sidecars? | `operaciones-canon.md` |
| ¿Cómo aprende el sistema? ¿Cómo fluye una lección? | `aprendizaje.md` |
| ¿Dónde viven los eventos? ¿Qué pasó con PULSE? | `eventos-timelog.md` |
| ¿Qué falta para que el corpus vivo cumpla el canon? | `migracion.md` |
| ¿Qué hace el código hoy vs lo que el canon exige? | `conformidad.md` |

## Documentos

### `formato.md` — reglas físicas transversales
Qué es un `.cortex`, los niveles 0–3, `$0:format`, declaraciones
ejecutables, la regla `ARQX:artifact` (primera entrada del cuerpo),
strict vs tolerant, el contrato del writer.

### `artefactos.md` — censo completo
TODA clase de artefacto `.cortex` del framework: brains, meta-brain,
identidades, skills, timelogs, policies, ciclos, issues, audits,
reports, contexts, templates, scripts, backups, archive y los
deprecados/eliminados. Nivel, ubicación, naturaleza, ciclo de vida,
reglas transversales.

### `cerebro-canon.md` — canon de secciones (GRADIENT-12)
El eje `$N` = distancia a la verdad, el principio de composición
(NATURALEZA→SCOPE→GRADIENTE→EXISTENCIA), el layout de 12 secciones,
las reglas de escritura y el mapa sigilo→sección. Incluye las notas de
por qué NO existen `PULSE`, `HANDOFFS`, `ISSUES`, `CONCURRENCY` ni
`ARQUX_METADATA`.

### `meta-cerebro-canon.md` — canon del meta-brain
El mismo eje `$N` aplicado al scope workspace: layout actual real,
layout propuesto GRADIENT-12, `REGISTRY` unificado (PROJECTS+AGENTS),
y las cuestiones de diseño abiertas (`$8` transversal, `SESSIONS`).

### `identidad-canon.md` — canon de identidad (Nivel 1)
El contrato conductual de agente: `$1 IDENTITY`, `$2 AXIOMS`,
`$3 LIMITS`, `$4 DESCRIPTION` — con la variante `$4 EXPERTISE` +
`$5 DESCRIPTION` (heimdall/seshat). Contrato, no almacén — solo crece
por elevación supervisada desde el router (`BEHAVIORAL LESSONS`
deprecado).

### `timelog-canon.md` — canon del timelog de sesión
El artefacto append-only intra-sesión: `$1 IDENTITY`, `$2 ACTIVITIES`,
`$3 RECEIPTS`, `$4 PROJECTIONS`, **`$5 EVENTS`** (modelo-destino —
hoy `record_pulse` escribe `AUD` a `$7` **posicional** = `ACTIVE_CONTEXT`,
colisión activa hasta G-3b). Lock propio, nunca podado.

### `habilidad-canon.md` — canon de skills (nivel 2)
Tres variantes físicas reales (`$N` seccionado, frontmatter YAML,
puro sobre) — ningún `.skill.md` declara `$0:format`. Sigilos
ejecutables dominantes `AXM`/`STP`/`IDN`/`HDL`; `workflows/` como
patrón índice+subdir.

### `registro-canon.md` — canon de `learn-policies.cortex`
Config ejecutable del motor (POL/THR/perillas) — una por proyecto.
Incluye la nota G-8: `agents`/`context`/`projects` ya no son archivos —
viven en meta-brain `$10`/`$7`.

### `gobernanza-canon.md` — canon de ciclo de vida
`cycles/<CYCLE-NN>/` como artefacto compuesto (cycle.cortex +
MANIFEST + blueprints/ + tasks/) e `issues/` con sus dos generaciones
(`.issue.md` legado archivado en G-8).

### `operaciones-canon.md` — canon de artefactos operativos
`audits/`, `reports/`, `archive/`, `backups/`, `contexts/`,
`templates/` y los sidecars (`.bak`/`.pre-migracion`/`.lock`):
salida vs store, retiro vs precaución.

### `aprendizaje.md` — motor de aprendizaje
El router naturaleza×scope (destinos paralelos desde `$8`, identidad
siempre supervisada), el motor tal como funciona hoy, y la propuesta de
dinámica (clustering temático, señal-densidad, modos, drenaje de `$8`,
activación asimétrica open-pesado/close-ligero). Pendiente: validación
de la propuesta con el Arquitecto.

### `eventos-timelog.md` — ciclo de vida de eventos
`$5 EVENTS` del timelog (modelo-destino): emisión, IDs `SESNNN-EXXXX`,
durabilidad real (nunca podado), consulta por-sesión vs cross-sesión,
el legado de los **276 AUD** archivados, y T1 — que sigue activo en
`pulse.py` (no solo referencia).

### `conformidad.md` — matriz código↔canon
Instrumento de revisión: por cada componente (constants, writers,
readers, emisores, consumidores) qué hace hoy con evidencia file:line,
qué exige el canon, la brecha y el protocolo de verificación por fila.
Orden de ejecución G-9→G-2→G-3→G-3b→G-4→G-5→G-7.

### `migracion.md` — deuda de reconciliación
G-1..G-9: G-8/G-8b consolidación **ejecutada** (2026-11-15); pendientes
G-2/G-3/G-3b (writers+validator+$5 EVENTS), G-4 drift, G-5 motor
(esperando spec), G-7 `OBJ:_`, **G-9 readers huérfanos** — el fallback
de lectura ya está degradado y los writers eliminados resucitan.

## Referencias hermanas

- `niveles-cortex-arqux.md` — modelo de niveles
- `docs/en/explicacion/frontera-codec.md` — frontera ArqUX/CODEC (espejo EN)
- `docs/es/especificacion/secciones-cerebro-canon.md` — *stub histórico →
  redirige aquí* (contenido movido a esta carpeta, 2026-11-15)

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
