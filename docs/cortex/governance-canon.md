# Canon — artefactos de ciclo de vida (`cycles/`, `issues/`)

**Estado:** canon vigente (ALFRED · CYCLE-16 · 2026-11-15, post-G-8,
auditado por Heimdall).
**Alcance:** `<project>/.arqux/cycles/` e `issues/`.

---

## 1. El ciclo — artefacto compuesto

Un ciclo NO es un archivo: es un **directorio**:

```
.arqux/cycles/CYCLE-NN/
├── cycle.cortex        ficha del ciclo
├── MANIFEST.md         índice humano (frontmatter + <!-- CYCLE:N --> + §1-§9)
├── blueprints/         BLP-NNN.md — un archivo por blueprint
└── tasks/              T-NNN.cortex — una por tarea
```

Subdirectorios **opcionales por ciclo**: varios ciclos carecen de
`tasks/` o `blueprints/`; **CYCLE-11 diverge** — porta `BLP-NNN/` como
directorios (cada uno `BLP-NNN.md` + `HEIMDALL_AUDIT.md`) más
`FINAL_REPORT.md`/`FINAL_AUDIT.md` en raíz.

### `cycle.cortex` (level 2)

`$0` glosario + `$19 ARQUX METADATA` (`ARQX:artifact`, posición
**legacy vigente**) + `$1 CYCLE` con `WRK:cycle{state, obj, ...}`.
No usa sigilos `CYC`/`PHS` — el ciclo es un `WRK` del proyecto.

### `blueprints/BLP-NNN.md` — NO son `.cortex`

Frontmatter YAML (`blueprint_id`, `title`, `cycle`, `status`,
`governor`, `executor`, `blp_markers@`, `evidence`, `quality_gates@`)
+ cuerpo markdown `§1..§18` con marcadores `<!-- BLP:N -->`. Son 18
secciones markdown, no CODEC.

### `tasks/T-NNN.cortex` (level 2)

`$19` + `$1 TASK` (`WRK:task`) + `$2 OBJECTIVE` (`OBJ`) +
`$3 PRECONDITIONS` (`CNST:pre*`) + `$4 ACCEPTANCE` (`CLAIM:ac*`) +
`$5 EVIDENCE` (`AUD:evidence`).

### `MANIFEST.md`

Frontmatter YAML (`cycle_id`, `project_ref`, `quality_gates@`) +
marcadores `<!-- CYCLE:N -->` + `§1`-`§9`. Defecto real conocido:
`CYCLE-16/MANIFEST.md:25` conserva `# Manifiesto: {name}` sin
renderizar (deuda de template).

Regla de scope (`AXM:blp_project_path_0001`): toda operación
`cycle.*`/`blueprint.*` usa `path=PROJECT_ROOT`, nunca workspace.

## 2. El issue — un formato `.cortex`, dos layouts internos

| Layout | Archivo | `$1` |
|---|---|---|
| `CONTENT` | `2026-07-16-*.cortex` | `$1 CONTENT` |
| `ISSUE RECORD` | `2026-09-29-*.cortex` | `$1 ISSUE RECORD` |

- **Nombrado real**: por archivo `<YYYY-MM-DD>-<slug>.cortex` +
  `IDN:issue{status}` interno. **El sigilo `ISS:` no existe** en el
  corpus ni en el código (solo en un fixture de test).
- `ARQX:artifact{level:0, name, usage:"state", kind:"native"}` en `$1`
  (reparado 2026-11-15 — la fusión `$19→$1` había dejado attrs sin
  coma).
- Generación anterior `.issue.md` (cabecera `# ISSUE:`/`# Severity:`
  + `## PROBLEM`/`## CONTEXT`/`## LESSON` — **sin frontmatter YAML**):
  **retirada de ARQUX en G-8** pero sigue siendo el formato dominante
  en `issues/` de otros proyectos (Conquistadores 46, CODEC-CORTEX
  16, Manhattan 24 — conteo directo) — migración workspace-wide
  pendiente.
- El brain no indexa issues — `ISSUES` eliminada del canon; abiertos =
  query por `status` sobre el directorio.
- Handoff ≠ issue: es `HND:<to>` en brain `$7` (estado pendiente).
- Formato/handler documentados en `arqux-issues.skill.md` (nivel
  proyecto).

## 3. Reglas

1. **Ciclo = carpeta, no archivo** — `MANIFEST.md` índice humano;
   `cycle.cortex` ficha gobernada.
2. **BLP = `.md`+frontmatter, task/cycle = `.cortex`** — dos dialectos
   conviven por diseño: los BLP son documento editorial, los demás
   son artefacto codec.
3. **`synthesize` primero** — `AXM:blp_synthesize_first_0002`.
4. **Issue = documento de contenido único** — `$1`, sin secciones
   internas tipo brain.
5. Mutación solo por `cycle.*` / `blueprint.*` / `task.*` / `issue.*`.

## 4. Referencias

- `artifacts.md` §2.6–2.7 — fichas
- `ops-canon.md` — auditorías dentro de cycles (`HEIMDALL_AUDIT.md`)
- `brain-canon.md` §1.3 — por qué issues no viven en el brain
