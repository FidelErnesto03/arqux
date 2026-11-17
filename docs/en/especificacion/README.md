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

# `docs/en/especificacion/` — the `.cortex` domain of the ArqUX framework

*English translation — canonical source: `docs/es/especificacion/README.md`*

Everything a `.cortex` IS, where each artifact lives, how the brain is
composed and how the system learns. Documents separated by the
**question** they answer.

> **Normative authority:** the ES corpus is **the source corpus** — the
> documents were written natively in Spanish; this EN mirror is a
> translation. In any future divergence between translations, the ES
> corpus wins. The cited `.cortex` artifacts (sigils, entries,
> examples) remain literal: the format itself is not translated.

## Reading map by question

| Question | Document |
|---|---|
| What is a `.cortex`? Which physical rules apply to all? | `formato.md` |
| Which artifacts exist and where does each live? | `artefactos.md` |
| How is the brain organized? Where does this datum go? | `cerebro-canon.md` |
| And the workspace meta-brain? | `meta-cerebro-canon.md` |
| And an identity/agent contract? | `identidad-canon.md` |
| And a session timelog? | `timelog-canon.md` |
| And a skill (level 2)? | `habilidad-canon.md` |
| And learn-policies? Where do registries live? | `registro-canon.md` |
| And cycles, BLPs, tasks, issues? | `gobernanza-canon.md` |
| And audits, archive, backups, sidecars? | `operaciones-canon.md` |
| How does the system learn? How does a lesson flow? | `aprendizaje.md` |
| Where do events live? What happened to PULSE? | `eventos-timelog.md` |
| What is missing for the live corpus to meet the canon? | `migracion.md` |
| What does the code do today vs what the canon demands? | `conformidad.md` |

## Documents

### `formato.md` — transversal physical rules
What a `.cortex` is, levels 0–3, `$0:format`, executable
declarations, the `ARQX:artifact` rule (first body entry),
strict vs tolerant, the writer contract.

### `artefactos.md` — complete census
EVERY class of `.cortex` artifact in the framework: brains, meta-brain,
identities, skills, timelogs, policies, cycles, issues, audits,
reports, contexts, templates, scripts, backups, archive and the
deprecated/removed ones. Level, location, nature, lifecycle,
transversal rules.

### `cerebro-canon.md` — section canon (GRADIENT-12)
The `$N` axis = distance to truth, the composition principle
(NATURE→SCOPE→GRADIENT→EXISTENCE), the 12-section layout,
the write rules and the sigil→section map. Includes the notes on
why `PULSE`, `HANDOFFS`, `ISSUES`, `CONCURRENCY` and
`ARQUX_METADATA` do NOT exist.

### `meta-cerebro-canon.md` — meta-brain canon
The same `$N` axis applied to workspace scope: real current layout,
proposed GRADIENT-12 layout, unified `REGISTRY` (PROJECTS+AGENTS),
and the open design questions (transversal `$8`, `SESSIONS`).

### `identidad-canon.md` — identity canon (Level 1)
An agent's behavioral contract: `$1 IDENTITY`, `$2 AXIOMS`,
`$3 LIMITS`, `$4 DESCRIPTION` — with the `$4 EXPERTISE` +
`$5 DESCRIPTION` variant (heimdall/seshat). Contract, not storage —
grows only by supervised elevation from the router (`BEHAVIORAL
LESSONS` deprecated).

### `timelog-canon.md` — session timelog canon
The intra-session append-only artifact: `$1 IDENTITY`, `$2 ACTIVITIES`,
`$3 RECEIPTS`, `$4 PROJECTIONS`, **`$5 EVENTS`** (destination model —
today `record_pulse` writes `AUD` to **positional** `$7` = `ACTIVE_CONTEXT`,
active collision until G-3b). Own lock, never pruned.

### `habilidad-canon.md` — skills canon (level 2)
Three real physical variants (`$N` sectioned, YAML frontmatter,
pure envelope) — no `.skill.md` declares `$0:format`. Dominant
executable sigils `AXM`/`STP`/`IDN`/`HDL`; `workflows/` as the
index+subdir pattern.

### `registro-canon.md` — `learn-policies.cortex` canon
The engine's executable config (POL/THR/knobs) — one per project.
Includes the G-8 note: `agents`/`context`/`projects` are no longer
files — they live in meta-brain `$10`/`$7`.

### `gobernanza-canon.md` — lifecycle canon
`cycles/<CYCLE-NN>/` as a composite artifact (cycle.cortex +
MANIFEST + blueprints/ + tasks/) and `issues/` with its two
generations (legacy `.issue.md` archived in G-8).

### `operaciones-canon.md` — operative artifacts canon
`audits/`, `reports/`, `archive/`, `backups/`, `contexts/`,
`templates/` and the sidecars (`.bak`/`.pre-migracion`/`.lock`):
output vs store, retirement vs precaution.

### `aprendizaje.md` — learning engine
The nature×scope router (parallel destinations from `$8`, identity
always supervised), the engine as it works today, and the dynamics
proposal (thematic clustering, signal-density, modes, `$8` drainage,
asymmetric open-heavy/close-light activation). Pending: validation
of the proposal with the Architect.

### `eventos-timelog.md` — event lifecycle
Timelog `$5 EVENTS` (destination model): emission, `SESNNN-EXXXX`
IDs, real durability (never pruned), per-session vs cross-session
query, the legacy of the **276 archived AUDs**, and T1 — still
active in `pulse.py` (not just reference).

### `conformidad.md` — code↔canon matrix
Review instrument: for each component (constants, writers,
readers, emitters, consumers) what it does today with file:line
evidence, what the canon demands, the gap and the per-row
verification protocol. Execution order G-9→G-2→G-3→G-3b→G-4→G-5→G-7.

### `migracion.md` — reconciliation debt
G-1..G-9: G-8/G-8b consolidation **executed** (2026-11-15); pending
G-2/G-3/G-3b (writers+validator+$5 EVENTS), G-4 drift, G-5 engine
(awaiting spec), G-7 `OBJ:_`, **G-9 orphan readers** — the read
fallback is already degraded and the removed writers resurrect.

## Sibling references

- `niveles-cortex-arqux.md` — levels model
- `docs/en/explicacion/frontera-codec.md` — ArqUX/CODEC boundary
- `docs/es/especificacion/secciones-cerebro-canon.md` — *historical
  stub → redirects here* (content moved to this folder, 2026-11-15)

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
