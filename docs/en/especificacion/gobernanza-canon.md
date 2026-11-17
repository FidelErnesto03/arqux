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
<p align="center"><sub>Canon · Normative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Canon — lifecycle artifacts (`cycles/`, `issues/`)

*English translation — canonical source: `docs/es/especificacion/gobernanza-canon.md`*

**Status:** current canon (ALFRED · CYCLE-16 · 2026-11-15, post-G-8,
audited by Heimdall).
**Scope:** `<project>/.arqux/cycles/` and `issues/`.

---

## 1. The cycle — composite artifact

A cycle is NOT a file: it is a **directory**:

```
.arqux/cycles/CYCLE-NN/
├── cycle.cortex        cycle card
├── MANIFEST.md         human index (frontmatter + <!-- CYCLE:N --> + §1-§9)
├── blueprints/         BLP-NNN.md — one file per blueprint
└── tasks/              T-NNN.cortex — one per task
```

**Optional per-cycle subdirectories**: several cycles lack
`tasks/` or `blueprints/`; **one cycle diverges** — it carries
`BLP-NNN/` as directories (each with `BLP-NNN.md` +
`HEIMDALL_AUDIT.md`) plus `FINAL_REPORT.md`/`FINAL_AUDIT.md` at root.

### `cycle.cortex` (level 2)

`$0` glossary + `$19 ARQUX METADATA` (`ARQX:artifact`, **current
legacy** position) + `$1 CYCLE` with `WRK:cycle{state, obj, ...}`.
It does not use `CYC`/`PHS` sigils — the cycle is a project `WRK`.

### `blueprints/BLP-NNN.md` — NOT `.cortex`

YAML frontmatter (`blueprint_id`, `title`, `cycle`, `status`,
`governor`, `executor`, `blp_markers@`, `evidence`, `quality_gates@`)
+ markdown body `§1..§18` with `<!-- BLP:N -->` markers. They are 18
markdown sections, not CODEC.

### `tasks/T-NNN.cortex` (level 2)

`$19` + `$1 TASK` (`WRK:task`) + `$2 OBJECTIVE` (`OBJ`) +
`$3 PRECONDITIONS` (`CNST:pre*`) + `$4 ACCEPTANCE` (`CLAIM:ac*`) +
`$5 EVIDENCE` (`AUD:evidence`).

### `MANIFEST.md`

YAML frontmatter (`cycle_id`, `project_ref`, `quality_gates@`) +
`<!-- CYCLE:N -->` markers + `§1`-`§9`. Known real defect:
one MANIFEST keeps `# Manifiesto: {name}` unrendered (template debt).

Scope rule (`AXM:blp_project_path_0001`): every `cycle.*`/`blueprint.*`
operation uses `path=PROJECT_ROOT`, never workspace.

## 2. The issue — one `.cortex` format, two internal layouts

| Layout | File | `$1` |
|---|---|---|
| `CONTENT` | `2026-07-16-*.cortex` | `$1 CONTENT` |
| `ISSUE RECORD` | `2026-09-29-*.cortex` | `$1 ISSUE RECORD` |

- **Real naming**: per file `<YYYY-MM-DD>-<slug>.cortex` +
  internal `IDN:issue{status}`. **The `ISS:` sigil does not exist**
  in the corpus or the code (only in a test fixture).
- `ARQX:artifact{level:0, name, usage:"state", kind:"native"}` in `$1`
  (repaired 2026-11-15 — the `$19→$1` merge had left attrs without
  commas).
- Previous `.issue.md` generation (`# ISSUE:`/`# Severity:` header
  + `## PROBLEM`/`## CONTEXT`/`## LESSON` — **no YAML frontmatter**):
  **retired from ARQUX in G-8** but still the dominant format in
  other projects' `issues/` (Conquistadores 46, CODEC-CORTEX 16,
  Manhattan 24 — direct count) — workspace-wide migration pending.
- The brain does not index issues — `ISSUES` removed from canon;
  open ones = query by `status` over the directory.
- Handoff ≠ issue: it is `HND:<to>` in brain `$7` (pending state).
- Format/handler documented in `arqux-issues.skill.md` (project
  level).

## 3. Rules

1. **Cycle = folder, not file** — `MANIFEST.md` human index;
   `cycle.cortex` governed card.
2. **BLP = `.md`+frontmatter, task/cycle = `.cortex`** — two dialects
   coexist by design: BLPs are editorial documents, the others are
   codec artifacts.
3. **`synthesize` first** — `AXM:blp_synthesize_first_0002`.
4. **Issue = single-content document** — `$1`, no brain-like internal
   sections.
5. Mutation only via `cycle.*` / `blueprint.*` / `task.*` / `issue.*`.

## 4. References

- `artefactos.md` §2.6–2.7 — cards
- `operaciones-canon.md` — audits inside cycles (`HEIMDALL_AUDIT.md`)
- `cerebro-canon.md` §1.3 — why issues do not live in the brain

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
