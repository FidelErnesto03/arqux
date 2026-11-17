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

# Canon — artefactos operativos (`audits`, `reports`, `archive`, `backups`, `contexts`, `templates`, `scripts`, `sidecars`)

**Estado:** canon vigente (ALFRED · CYCLE-16 · 2026-11-15, auditado
por Heimdall).

---

## 1. El mapa (niveles verificados)

| Artefacto | Ubicación | Formato | Función |
|---|---|---|---|
| `audits/` | `<project>/.arqux/` **y `docs/audits/`** (o el área interna del equipo, si el contenido no se publica) | `.md`/`.cortex` | auditorías — producto de operación |
| `reports/` | `<project>/.arqux/` | `.md` | reportes de revisión (Heimdall/otros) |
| `archive/` | ambos niveles | dir por fecha (`hygiene-YYYY-MM-DD/`) **+ `.arqux.prev/`** (snapshot completo pre-operación) | retiro digno |
| `backups/` | `<project>/.arqux/` | dir por causa (`<fecha>-<causa>/` o `<causa>/` — fecha opcional) | precaución antes de operación |
| `contexts/` | `<ws>/.arqux/` | `.cortex` | contextos de ejecución **vivos** (`exec-*.cortex`) |
| `templates/` | `<ws>/.arqux/` | `.md`/`.cortex`/`.yaml` | plantillas de artefacto |
| `scripts/` | `<project>/.arqux/` | `.py`/`.sh` | hooks de enforcement (`arqux_response_hook.py`, `arqux_session_gate.sh`) |
| `*.bak`, `*.pre-migracion`, `*.lock`, `sentinel.txt` | al lado del artefacto | sidecar | mecanismo, no artefacto |

## 2. Reglas por clase

### `audits/` y `reports/` — salida, no store

Producto de una operación; se citan como evidencia, nunca se
reescriben. Nombrado mixto real (fecha/autor **y** por-ciclo);
variante `.cortex` en `docs/audits/`. También existen auditorías
**dentro** de cycles (`HEIMDALL_AUDIT.md`, `FINAL_AUDIT.md` en
CYCLE-11; `audit-BLP-004.hcortex.md` en CYCLE-06).

### `archive/` — retiro digno

Dos patrones reales: `hygiene-YYYY-MM-DD/` (higiene deliberada) y
`.arqux.prev/` (snapshot completo del `.arqux` anterior, con
`sentinel.txt`). Archive ≠ backups: retiro deliberado vs precaución
pre-operación.

### `backups/` — precaución con causa

`<causa>/` con fecha opcional — nunca genérico. Set real ARQUX:
`blp001-pre-dialect/` (backup **binario**
`corpus-pre-migracion.tar.gz`), `blp001-remigracion/` (porta un
`meta-brain.cortex` de **workspace** — contaminación de nivel
conocida), `2026-11-14-corrupcion-cruzada/` (`BLP-001/002.md`).

### `contexts/` — punteros per-execution (vivos)

`exec-<id>.cortex`: contexto de la ejecución en curso — el puntero
**ganador** sobre el eliminado `context.cortex` (`_project.py`
`_context_candidates`). Layout: `$0` + `$1 CURRENT` + `$19`.

### `templates/` — el molde

Set real: `AGENTS.full/lite.md`, `BLP_TEMPLATE.md`,
`CYCLE_MANIFEST_TEMPLATE.md`, `brain.{cortex,md,yaml}`,
`meta-brain.{cortex,md}`, `learn-policies.cortex`. Tres formatos;
se instancian, no se gobiernan.

### `scripts/` — enforcement activo

Los hooks que AGENTS invoca (pre-turn gate, pre-response header).
Son código ejecutable dentro de `.arqux/` — único caso de ejecutable
en la frontera gobernada.

### Sidecars — mecanismo, no contenido

- `*.lock` — transitorio por escritura (hoy: `meta-brain.cortex.lock`,
  `alfred.cortex.lock`)
- `*.bak` — pre-escritura del writer; el residuo saneado vive en
  `archive/hygiene-2026-11-15/bak-residue/`
- `*.pre-migracion` — congelado antes de migración de formato
- `sentinel.txt` — marca de snapshot en archive

### Eliminados en G-8 (2026-11-15)

- `loops/` (ARQUX) — su estado vive en brain `$9 LOOPS`. **Nota**: el
  directorio SÍ tiene propósito de diseño — es el transporte WAKE de
  loops autónomos (`autonomia.skill.md`) y sigue activo en otros
  proyectos (EXPERTA); en ARQUX nunca ganó contenido.
- `packages/` (ambos niveles) — staging, renacerán si se necesitan.
- `contexts/` (proyecto) — los exec-contexts viven solo en workspace.

## 3. Referencias

- `artefactos.md` §1 — censo completo
- `gobernanza-canon.md` — cycles/issues
- `migracion.md` — barridos ejecutados

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
