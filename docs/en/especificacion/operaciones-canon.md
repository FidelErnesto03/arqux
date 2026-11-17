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

# Canon — operative artifacts (`audits`, `reports`, `archive`, `backups`, `contexts`, `templates`, `scripts`, `sidecars`)

*English translation — canonical source: `docs/es/especificacion/operaciones-canon.md`*

**Status:** current canon (ALFRED · CYCLE-16 · 2026-11-15, audited
by Heimdall).

---

## 1. The map (verified levels)

| Artifact | Location | Format | Function |
|---|---|---|---|
| `audits/` | `<project>/.arqux/` **and `docs/audits/`** (or the team's internal area, if content is not published) | `.md`/`.cortex` | audits — operation output |
| `reports/` | `<project>/.arqux/` | `.md` | review reports (Heimdall/others) |
| `archive/` | both levels | per-date dir (`hygiene-YYYY-MM-DD/`) **+ `.arqux.prev/`** (full pre-operation snapshot) | dignified retirement |
| `backups/` | `<project>/.arqux/` | per-cause dir (`<date>-<cause>/` or `<cause>/` — date optional) | pre-operation precaution |
| `contexts/` | `<ws>/.arqux/` | `.cortex` | **live** execution contexts (`exec-*.cortex`) |
| `templates/` | `<ws>/.arqux/` | `.md`/`.cortex`/`.yaml` | artifact templates |
| `scripts/` | `<project>/.arqux/` | `.py`/`.sh` | enforcement hooks (`arqux_response_hook.py`, `arqux_session_gate.sh`) |
| `*.bak`, `*.pre-migracion`, `*.lock`, `sentinel.txt` | beside the artifact | sidecar | mechanism, not artifact |

## 2. Rules by class

### `audits/` and `reports/` — output, not store

Product of an operation; cited as evidence, never rewritten. Real
mixed naming (date/author **and** per-cycle); `.cortex` variant in
`docs/audits/`. Audits also exist **inside** cycles
(`HEIMDALL_AUDIT.md`, `FINAL_AUDIT.md` in a prior cycle;
`audit-BLP-004.hcortex.md` in another).

### `archive/` — dignified retirement

Two real patterns: `hygiene-YYYY-MM-DD/` (deliberate hygiene) and
`.arqux.prev/` (full snapshot of the previous `.arqux`, with
`sentinel.txt`). Archive ≠ backups: deliberate retirement vs
pre-operation precaution.

### `backups/` — precaution with cause

`<cause>/` with optional date — never generic. Real ARQUX set:
`blp001-pre-dialect/` (**binary** backup
`corpus-pre-migracion.tar.gz`), `blp001-remigracion/` (carries a
**workspace** `meta-brain.cortex` — known level contamination),
`2026-11-14-corrupcion-cruzada/` (`BLP-001/002.md`).

### `contexts/` — per-execution pointers (live)

`exec-<id>.cortex`: the in-flight execution's context — the
**winning** pointer over the removed `context.cortex` (`_project.py`
`_context_candidates`). Layout: `$0` + `$1 CURRENT` + `$19`.

### `templates/` — the mold

Real set: `AGENTS.full/lite.md`, `BLP_TEMPLATE.md`,
`CYCLE_MANIFEST_TEMPLATE.md`, `brain.{cortex,md,yaml}`,
`meta-brain.{cortex,md}`, `learn-policies.cortex`. Three formats;
they are instantiated, not governed.

### `scripts/` — active enforcement

The hooks AGENTS invokes (pre-turn gate, pre-response header).
Executable code inside `.arqux/` — the only executable case on the
governed boundary.

### Sidecars — mechanism, not content

- `*.lock` — transient per write (today: `meta-brain.cortex.lock`,
  `alfred.cortex.lock`)
- `*.bak` — writer pre-write; the sanitized residue lives in
  `archive/hygiene-2026-11-15/bak-residue/`
- `*.pre-migracion` — frozen before a format migration
- `sentinel.txt` — snapshot mark in archive

### Removed in G-8 (2026-11-15)

- `loops/` (ARQUX) — its state lives in brain `$9 LOOPS`. **Note**: the
  directory DOES have a design purpose — it is the WAKE transport of
  autonomous loops (`autonomia.skill.md`) and stays active in other
  projects (EXPERTA); in ARQUX it never gained content.
- `packages/` (both levels) — staging; reborn if needed.
- `contexts/` (project) — exec-contexts live only in workspace.

## 3. References

- `artefactos.md` §1 — full census
- `gobernanza-canon.md` — cycles/issues
- `migracion.md` — executed sweeps

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
