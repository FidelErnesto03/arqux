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

# Census of `.cortex` artifacts in the ArqUX framework

*English translation — canonical source: `docs/es/especificacion/artefactos.md`*

**Status:** current inventory (ALFRED · CYCLE-16 · 2026-11-15).
**Purpose:** every class of `.cortex` artifact that exists in the
framework — what it is, where it lives, who writes it and how it
dies. The common physical format in `formato.md`; the brain's
internal canon in `cerebro-canon.md`.

---

## 1. Master table

| Artifact | Level | Location | Nature | Lifecycle |
|---|---|---|---|---|
| `brain.cortex` | 3 | `<project>/.arqux/` | project inter-session memory | permanent, GRADIENT-12 canon |
| `meta-brain.cortex` | 3 | `<workspace>/.arqux/` | workspace memory (projects, DOMs) | permanent |
| `identities/<agent>.cortex` | 1 | `<workspace>/.arqux/identities/` | agent behavioral contract | permanent, grows by supervised elevation |
| `skills/*.skill.md` | 2 | `.arqux/skills/` | reusable capability (.cortex envelope + markdown body) | permanent, versioned by author |
| `timelog/SESNNN_*.cortex` | 0 | `<project>/.arqux/timelog/` | intra-session memory: intervals + events + receipts | append-only, never pruned |
| `learn-policies.cortex` | 2 | `<project>/.arqux/` (one per project) | engine policies: `POL`/`THR`/`PRT` + blocks | in-place, no mutation handler today |
| `cycles/CYCLE-NN/` (composite dir) | 2 | `<project>/.arqux/cycles/` | `cycle.cortex` + `MANIFEST.md` + `blueprints/BLP-NNN.md` + `tasks/T-NNN.cortex` | cycle life; archive on close |
| `issues/<date>-<slug>.cortex` | 0 | `<project>/.arqux/issues/` | one file per issue | lives until close/verify |
| `audits/` | 0 | `<project>/.arqux/` and `docs/audits/` (or internal area if unpublished) | audits — operation output | append-only |
| `reports/` | 0 | `<project>/.arqux/reports/` | generated reports | append-only |
| `contexts/exec-*.cortex` | 0 | `<ws>/.arqux/contexts/` | live execution contexts | transient per execution |
| `templates/` | template | `<ws>/.arqux/templates/` | `.md`/`.cortex`/`.yaml` molds | in-place |
| `scripts/` | executable | `<project>/.arqux/scripts/` | enforcement hooks | versioned |
| `backups/` | copy | `.arqux/backups/` | per-cause safety copies | operational |
| `archive/` | history | `.arqux/archive/` | dignified retirement (hygiene sweeps, legacy) | never touched |
| `lessons.cortex` | — | `.arqux/` | **DEPRECATED** — lessons live in brain `$8` | legacy-read only |

## 2. Detail by family

### 2.1 Memories (level 3)

**`brain.cortex`** — the project: identity, constitution, truth,
state, lesson queue, session index. Full canon in
`cerebro-canon.md`. Read first (`AXM:brain_first`), written only
by MCP handlers.

**`meta-brain.cortex`** — the workspace: governed projects,
reconciled DOMs, inter-project state. Own canon:
`meta-cerebro-canon.md` (GRADIENT-12 applied to workspace scope).

### 2.2 Agent contract (level 1)

**`identities/<agent>.cortex`** — `ARQX:artifact{level:1}` first,
`IDN`, behavioral `AXM`/`LIM`, `DESC`/`ROLE`. Own canon:
`identidad-canon.md`. Grows **only by supervised elevation** from
the funnel (aprendizaje.md §2): contracts, never a lesson store
(`BEHAVIORAL LESSONS` deprecated).

### 2.3 Capability (level 2)

**`skills/*.skill.md`** — `.cortex` envelope (frontmatter/declarations)
+ free markdown body by the author. The envelope is what is governed;
the body is content (payloads do not strict-parse by design).
Canon: `habilidad-canon.md`.

### 2.4 Intra-session memory

**`timelog/SESNNN_<ts>.cortex`** — `$1 IDENTITY` (`TLG:identity` with
`version`/`revision`), `$2 ACTIVITIES` (`ACT` intervals),
`$3 RECEIPTS` (`RCV`), `$4 PROJECTIONS` (`PRJ` external projection),
`$5 EVENTS` (`AUD`/`DEC`/`ERR` — destination model, see
`timelog-canon.md` + `eventos-timelog.md`). Append-only, never
pruned: the real durable evidence.

### 2.6 Operational governance

- **`learn-policies.cortex`** — `POL:from→to{action}` + `requires:"admin_policy"` +
  `THR`/`PRT`/`GTE`/`KNW` (truth in `registro-canon.md`; inert
  fields and missing mutation handler documented there).
- **`handoffs/<agent>.cortex`** — **removed in ws+ARQUX** (G-8b):
  the payload is pending state → 5 `HND:<to>` migrated to brain `$7`
  (orphan residue — no consumer). **Persists in other governed
  projects** (Conquistadores, CODEC-CORTEX, EXPERTA, Manhattan…) and
  `session.handoff` **recreates it on every invocation** — the real
  removal awaits the reroute (G-3b). The event → emitter's timelog
  `$5` (destination model).
- **Removed in G-8**: `agents.cortex`, `projects.cortex` →
  meta-brain `$10 REGISTRY`; `context.cortex` → meta-brain `$7`;
  ws `learn-policies.cortex` → one per project; `loops/`,
  `packages/`, `contexts/` (project) removed as empty.
- **Archived in G-8b**: `manifest.md`, `meta-brain.md`, `projects.md`
  (init narrative/template — nobody consumes them), remaining legacy
  `issues/*.md`, orphan `.sessions.lock` removed.

Group canon: `registro-canon.md`.

### 2.7 A cycle's lifecycle

`cycles/CYCLE-NN/` — composite directory: `cycle.cortex` (card,
`WRK:cycle`), `MANIFEST.md` (human index), `blueprints/BLP-NNN.md`
(frontmatter + `§1..§18` + `<!-- BLP:N -->` — **`.md`, not `.cortex`**),
`tasks/T-NNN.cortex`. They live while the cycle lives; on close the
cycle is archived (**declared policy — no cycle archived yet**;
all 16 remain in `cycles/`) — the synthesis already lives in `SES` +
lessons. Additional real pattern: nested `.arqux/` in
sub-projects (e.g. `Manhattan/BEX/.arqux`). Canon:
`gobernanza-canon.md`.

### 2.8 Per-file record

`issues/` (one file per issue — open ones derived by
`status`, no brain section — `gobernanza-canon.md`), `audits/`,
`reports/`, `contexts/` (`operaciones-canon.md`).

### 2.9 Operational

`templates/` (molds), `backups/`, `archive/` (dignified retirement —
`hygiene-2026-11-15/` includes `pulse-legacy.cortex` with **276 AUD**,
`bak-residue/`, the retired init `.md`s). Canon: `operaciones-canon.md`.

### 2.10 Deprecated — legacy-read only

- **`lessons.cortex`** — replaced by brain `$8` (Architect rule
  2026-11-15).
- **`summary:*.cortex`** — historical pattern referenced in docs; no
  live instances in the current corpus.

## 3. Transversal rules (apply to ALL)

1. Mutation only via MCP handlers — never native editing (`.arqux/` is
   a governance boundary).
2. Every new write must be strict (`$0:format` + declarations +
   `ARQX:artifact` at the head of `$1`) — **goal**: the real corpus is
   mostly tolerant today (`formato.md` §4).
3. Historical append-only is not rewritten for cosmetics.
4. Per-file lock (sibling `.cortex.lock`), not per-directory.
5. `brain.cortex` is read BEFORE any exploration
   (`AXM:brain_first`); everything learned outside returns to the
   brain.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
