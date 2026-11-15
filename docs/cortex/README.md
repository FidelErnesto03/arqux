# `docs/cortex/` — el dominio `.cortex` del framework ArqUX

Todo lo que un `.cortex` ES, dónde vive cada artefacto, cómo se compone
el brain y cómo aprende el sistema. Documentos separados por la
**pregunta** que responden.

## Mapa de lectura por pregunta

| Pregunta | Documento |
|---|---|
| ¿Qué es un `.cortex`? ¿Qué reglas físicas aplican a todos? | `format.md` |
| ¿Qué artefactos existen y dónde vive cada uno? | `artifacts.md` |
| ¿Cómo está organizado el brain? ¿Dónde va este dato? | `brain-canon.md` |
| ¿Y el meta-brain del workspace? | `meta-brain-canon.md` |
| ¿Y el contrato de una identidad/agente? | `identity-canon.md` |
| ¿Y el timelog de una sesión? | `timelog-canon.md` |
| ¿Y un skill (nivel 2)? | `skill-canon.md` |
| ¿Y learn-policies? ¿Y dónde viven los registros? | `registry-canon.md` |
| ¿Y ciclos, BLPs, tareas, issues? | `governance-canon.md` |
| ¿Y audits, archive, backups, sidecars? | `ops-canon.md` |
| ¿Cómo aprende el sistema? ¿Cómo fluye una lección? | `learning.md` |
| ¿Dónde viven los eventos? ¿Qué pasó con PULSE? | `events-timelog.md` |
| ¿Qué falta para que el corpus vivo cumpla el canon? | `migration.md` |
| ¿Qué hace el código hoy vs lo que el canon exige? | `conformance.md` |

## Documentos

### `format.md` — reglas físicas transversales
Qué es un `.cortex`, los niveles 0–3, `$0:format`, declaraciones
ejecutables, la regla `ARQX:artifact` (primera entrada del cuerpo),
strict vs tolerant, el contrato del writer.

### `artifacts.md` — censo completo
TODA clase de artefacto `.cortex` del framework: brains, meta-brain,
identidades, skills, timelogs, policies, ciclos, issues, audits,
reports, contexts, templates, scripts, backups, archive y los
deprecados/eliminados. Nivel, ubicación, naturaleza, ciclo de vida,
reglas transversales.

### `brain-canon.md` — canon de secciones (GRADIENT-12)
El eje `$N` = distancia a la verdad, el principio de composición
(NATURALEZA→SCOPE→GRADIENTE→EXISTENCIA), el layout de 12 secciones,
las reglas de escritura y el mapa sigilo→sección. Incluye las notas de
por qué NO existen `PULSE`, `HANDOFFS`, `ISSUES`, `CONCURRENCY` ni
`ARQUX_METADATA`.

### `meta-brain-canon.md` — canon del meta-brain
El mismo eje `$N` aplicado al scope workspace: layout actual real,
layout propuesto GRADIENT-12, `REGISTRY` unificado (PROJECTS+AGENTS),
y las cuestiones de diseño abiertas (`$8` transversal, `SESSIONS`).

### `identity-canon.md` — canon de identidad (Nivel 1)
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

### `skill-canon.md` — canon de skills (nivel 2)
Tres variantes físicas reales (`$N` seccionado, frontmatter YAML,
puro sobre) — ningún `.skill.md` declara `$0:format`. Sigilos
ejecutables dominantes `AXM`/`STP`/`IDN`/`HDL`; `workflows/` como
patrón índice+subdir.

### `registry-canon.md` — canon de `learn-policies.cortex`
Config ejecutable del motor (POL/THR/perillas) — una por proyecto.
Incluye la nota G-8: `agents`/`context`/`projects` ya no son archivos —
viven en meta-brain `$10`/`$7`.

### `governance-canon.md` — canon de ciclo de vida
`cycles/<CYCLE-NN>/` como artefacto compuesto (cycle.cortex +
MANIFEST + blueprints/ + tasks/) e `issues/` con sus dos generaciones
(`.issue.md` legado archivado en G-8).

### `ops-canon.md` — canon de artefactos operativos
`audits/`, `reports/`, `archive/`, `backups/`, `contexts/`,
`templates/` y los sidecars (`.bak`/`.pre-migracion`/`.lock`):
salida vs store, retiro vs precaución.

### `learning.md` — motor de aprendizaje
El router naturaleza×scope (destinos paralelos desde `$8`, identidad
siempre supervisada), el motor tal como funciona hoy, y la propuesta de
dinámica (clustering temático, señal-densidad, modos, drenaje de `$8`,
activación asimétrica open-pesado/close-ligero). Pendiente: validación
de la propuesta con el Arquitecto.

### `events-timelog.md` — ciclo de vida de eventos
`$5 EVENTS` del timelog (modelo-destino): emisión, IDs `SESNNN-EXXXX`,
durabilidad real (nunca podado), consulta por-sesión vs cross-sesión,
el legado de los **276 AUD** archivados, y T1 — que sigue activo en
`pulse.py` (no solo referencia).

### `conformance.md` — matriz código↔canon
Instrumento de revisión: por cada componente (constants, writers,
readers, emisores, consumidores) qué hace hoy con evidencia file:line,
qué exige el canon, la brecha y el protocolo de verificación por fila.
Orden de ejecución G-9→G-2→G-3→G-3b→G-4→G-5→G-7.

### `migration.md` — deuda de reconciliación
G-1..G-9: G-8/G-8b consolidación **ejecutada** (2026-11-15); pendientes
G-2/G-3/G-3b (writers+validator+$5 EVENTS), G-4 drift, G-5 motor
(esperando spec), G-7 `OBJ:_`, **G-9 readers huérfanos** — el fallback
de lectura ya está degradado y los writers eliminados resucitan.

## Referencias hermanas

- `docs/architecture/niveles-cortex-arqux.md` — modelo de niveles
- `docs/architecture/codec-boundary.md` — frontera ArqUX/CODEC
- `docs/reference/cortex-brain-section-canon.md` — *stub histórico →
  redirige aquí* (contenido movido a esta carpeta, 2026-11-15)
