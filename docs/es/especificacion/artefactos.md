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

# Censo de artefactos `.cortex` del framework ArqUX

**Estado:** inventario vigente (ALFRED · CYCLE-16 · 2026-11-15).
**Propósito:** cada clase de artefacto `.cortex` que existe en el
framework — qué es, dónde vive, quién lo escribe y cómo muere.
El formato físico común en `formato.md`; el canon interno del brain en
`cerebro-canon.md`.

---

## 1. Tabla maestra

| Artefacto | Nivel | Ubicación | Naturaleza | Ciclo de vida |
|---|---|---|---|---|
| `brain.cortex` | 3 | `<project>/.arqux/` | memoria inter-sesión del proyecto | permanente, canon GRADIENT-12 |
| `meta-brain.cortex` | 3 | `<workspace>/.arqux/` | memoria del workspace (proyectos, DOMs) | permanente |
| `identities/<agent>.cortex` | 1 | `<workspace>/.arqux/identities/` | contrato conductual del agente | permanente, crece por elevación supervisada |
| `skills/*.skill.md` | 2 | `.arqux/skills/` | capacidad reutilizable (sobre .cortex + cuerpo markdown) | permanente, versionado por el autor |
| `timelog/SESNNN_*.cortex` | 0 | `<project>/.arqux/timelog/` | memoria intra-sesión: intervalos + eventos + recibos | append-only, nunca podado |
| `learn-policies.cortex` | 2 | `<project>/.arqux/` (una por proyecto) | políticas del motor: `POL`/`THR`/`PRT` + bloques | in-place, sin handler de mutación hoy |
| `cycles/CYCLE-NN/` (dir compuesto) | 2 | `<project>/.arqux/cycles/` | `cycle.cortex` + `MANIFEST.md` + `blueprints/BLP-NNN.md` + `tasks/T-NNN.cortex` | vida del ciclo; archive al cerrar |
| `issues/<fecha>-<slug>.cortex` | 0 | `<project>/.arqux/issues/` | un archivo por issue | vive hasta cierre/verify |
| `audits/` | 0 | `<project>/.arqux/` y `docs/audits/` (o área interna si no se publican) | auditorías — producto de operación | append-only |
| `reports/` | 0 | `<project>/.arqux/reports/` | informes generados | append-only |
| `contexts/exec-*.cortex` | 0 | `<ws>/.arqux/contexts/` | contextos de ejecución vivos | transitorio por ejecución |
| `templates/` | plantilla | `<ws>/.arqux/templates/` | moldes `.md`/`.cortex`/`.yaml` | in-place |
| `scripts/` | ejecutable | `<project>/.arqux/scripts/` | hooks de enforcement | versionado |
| `backups/` | copia | `.arqux/backups/` | copias de seguridad por causa | operacional |
| `archive/` | historia | `.arqux/archive/` | retiro digno (hygiene sweeps, legados) | nunca se toca |
| `lessons.cortex` | — | `.arqux/` | **DEPRECADO** — las lecciones viven en brain `$8` | lectura-legacy solamente |

## 2. Detalle por familia

### 2.1 Memorias (nivel 3)

**`brain.cortex`** — el proyecto: identidad, constitución, verdad,
estado, cola de lecciones, índice de sesiones. Canon completo en
`cerebro-canon.md`. Se lee primero (`AXM:brain_first`), se escribe solo
por handlers MCP.

**`meta-brain.cortex`** — el workspace: proyectos gobernados, DOMs
reconciliados, estado entre proyectos. Canon propio:
`meta-cerebro-canon.md` (GRADIENT-12 aplicado a scope workspace).

### 2.2 Contrato del agente (nivel 1)

**`identities/<agent>.cortex`** — `ARQX:artifact{level:1}` primero,
`IDN`, `AXM`/`LIM` conductuales, `DESC`/`ROLE`. Canon propio:
`identidad-canon.md`. Crece **solo por elevación supervisada** desde
el embudo (aprendizaje.md §2): contratos, nunca almacén de lecciones
(`BEHAVIORAL LESSONS` deprecado).

### 2.3 Capacidad (nivel 2)


**`skills/*.skill.md`** — sobre `.cortex` (frontmatter/declaraciones) +
cuerpo markdown libre del autor. El sobre es lo gobernado; el cuerpo
es contenido (los payloads no strict-parsean por diseño).
Canon: `habilidad-canon.md`.

### 2.4 Memoria intra-sesión

**`timelog/SESNNN_<ts>.cortex`** — `$1 IDENTITY` (`TLG:identity` con
`version`/`revision`), `$2 ACTIVITIES` (`ACT` intervalos),
`$3 RECEIPTS` (`RCV`), `$4 PROJECTIONS` (`PRJ` proyección externa),
`$5 EVENTS` (`AUD`/`DEC`/`ERR` — modelo-destino, ver
`timelog-canon.md` + `eventos-timelog.md`). Append-only, jamás podado:
la evidencia durable real.

### 2.6 Gobernanza operacional

- **`learn-policies.cortex`** — `POL:from→to{action}` + `requires:"admin_policy"` +
  `THR`/`PRT`/`GTE`/`KNW` (verdad en `registro-canon.md`; campos
  inertes y sin handler de mutación documentados allí).
- **`handoffs/<agent>.cortex`** — **eliminado en ws+ARQUX** (G-8b):
  el payload es estado pendiente → 5 `HND:<to>` migrados a brain `$7`
  (residuo huérfano — sin consumidor). **Persiste en otros proyectos
  gobernados** (Conquistadores, CODEC-CORTEX, EXPERTA, Manhattan…) y
  `session.handoff` lo **recrea en cada invocación** — la eliminación
  real espera el reroute (G-3b). El evento → timelog `$5` del emisor
  (modelo-destino).
- **Eliminados en G-8**: `agents.cortex`, `projects.cortex` →
  meta-brain `$10 REGISTRY`; `context.cortex` → meta-brain `$7`;
  ws `learn-policies.cortex` → una por proyecto; `loops/`,
  `packages/`, `contexts/` (proyecto) eliminados por vacíos.
- **Archivados en G-8b**: `manifest.md`, `meta-brain.md`, `projects.md`
  (narrativa/template de init — nadie los consume), `issues/*.md`
  legados restantes, `.sessions.lock` huérfano eliminado.

Canon del grupo: `registro-canon.md`.

### 2.7 Ciclo de vida de un ciclo

`cycles/CYCLE-NN/` — directorio compuesto: `cycle.cortex` (ficha,
`WRK:cycle`), `MANIFEST.md` (índice humano), `blueprints/BLP-NNN.md`
(frontmatter + `§1..§18` + `<!-- BLP:N -->` — **`.md`, no `.cortex`**),
`tasks/T-NNN.cortex`. Viven mientras el ciclo vive; al cerrar el
ciclo se archiva (**política declarada — ningún ciclo archivado aún**;
los 16 siguen en `cycles/`) — la síntesis ya quedó en `SES` +
lecciones. Patrón adicional real: `.arqux/` anidados en
sub-proyectos (p.ej. `Manhattan/BEX/.arqux`). Canon:
`gobernanza-canon.md`.

### 2.8 Registro por archivo

`issues/` (un archivo por issue — los abiertos se derivan por
`status`, sin sección en brain — `gobernanza-canon.md`), `audits/`,
`reports/`, `contexts/` (`operaciones-canon.md`).

### 2.9 Operacional

`templates/` (moldes), `backups/`, `archive/` (retiro digno —
`hygiene-2026-11-15/` incluye `pulse-legacy.cortex` con **276 AUD**,
`bak-residue/`, los `.md` de init retirados). Canon: `operaciones-canon.md`.

### 2.10 Deprecados — lectura-legacy solamente

- **`lessons.cortex`** — sustituido por brain `$8` (regla Arquitecto
  2026-11-15).
- **`summary:*.cortex`** — patrón histórico referenciado en docs; no
  hay instancias vivas en el corpus actual.

## 3. Reglas transversales (aplican a TODOS)

1. Mutación solo por handlers MCP — nunca edición nativa (`.arqux/` es
   frontera de gobernanza).
2. Toda escritura nueva debe ser strict (`$0:format` + declaraciones +
   `ARQX:artifact` en cabecera de `$1`) — **meta**: el corpus real es
   mayoritariamente tolerant hoy (`formato.md` §4).
3. Append-only histórico no se reescribe por cosmética.
4. Lock por archivo (`.cortex.lock` hermano), no por directorio.
5. `brain.cortex` se lee ANTES de cualquier exploración
   (`AXM:brain_first`); todo lo aprendido fuera vuelve al brain.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
