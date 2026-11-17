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

# Canon — `meta-brain.cortex` (Level 3 / workspace META-BRAIN)

*English translation — canonical source: `docs/es/especificacion/meta-cerebro-canon.md`*

**Status:** current canon applied to workspace scope (ALFRED ·
CYCLE-16 · 2026-11-15).
**Scope:** `<workspace>/.arqux/meta-brain.cortex` — the workspace's
memory: governed projects, agents, transversal focus. It is NOT a
project brain: the workspace is a container (`AXM:no_workspace_project`).

---

## 1. What it is

The *inter-project* memory: which projects the workspace governs, which
agents operate, the Architect's transversal focus. Same GRADIENT
philosophy as `cerebro-canon.md` — `$N` = distance to truth — with the
scope substitution: project → workspace.

## 2. Current layout (post-G-8 migration, 2026-11-15)

The file already migrated to the canonical layout — 38 entries,
`cortex_verify` valid=true:

| # | Title | Zone | Real content |
|---|---|---|---|
| $0 | `GLOSSARY` | envelope | `$0:format` + contracts (`FCS`/`KNW`/`OBJ`/`WRK` added in the repair; `cortex_verify` reports I001 informational auto-add — verifiable via handler) |
| $1 | `IDENTITY` | contract | `ARQX:artifact{level:3}` + `IDN:workspace{name, root, governor, projects:"18", status:"current"}` |
| $2 | `AXIOMS` | contract | empty — workspace constitution pending seeding |
| $3 | `KNOWLEDGE` | contract | operative transversal truth |
| $4 | `RISKS` | contract | empty |
| $5 | `FOCUS` | state | `FCS:current` |
| $6 | `OBJECTIVES` | state | `OBJ:workspace` |
| $7 | `ACTIVE_CONTEXT` | state | **`WRK:current{name:"workspace", project:"ARQUX", scope:"CYCLE-16", agent:"Alfred", ses:"SES021", project_root}`** — absorbed `context.cortex` |
| $8 | `LESSONS` | staging | empty — current rule: lessons only in the origin project's brain `$8` |
| $9 | `LOOPS` | system | empty |
| $10 | `REGISTRY` | system | `DOM:*` projects (18 — zero `PRJ:`; `PRJ` is the timelog projections sigil) + `IDN:*` agents (7: alfred, jarvis, heimdall, seshat, auditor, executor, governor) |

### 2b. Historical layout (pre-G-8)

`$1 META-BRAIN · $2 PROJECTS · $3 FOCUS · $4 AGENTS · $5 KNOWLEDGE`
+ `$19 ARQUX METADATA`. Physically migrated on 2026-11-15; other
governed projects may still be on this layout (workspace-wide
migration pending).

## 3. Defects resolved in the repair (Heimdall audit)

- `DOM:domain` (registry residue) — removed.
- `IDN:new-agent` (`agents.cortex` residue) — removed.
- Agent registry completed: 7 `IDN` (previously only 2).
- `$0` completed: `FCS`/`KNW`/`OBJ`/`WRK` declared.
- Open residue (verifier's I002): 5 placeholders in 4
  entries — `IDN:workspace{root:"<workspace-root>", created:"<timestamp>"}`,
  `FCS:current{updated:"<timestamp>"}`, `IDN:alfred`/`IDN:jarvis`
  `{adopted:"<timestamp>"}` — resolved on the next legitimate write.

## 4. Rules inherited from the brain canon

1. Same composition principle (`cerebro-canon.md` §1.3) — every
   data proposal passes the test.
2. `ARQX:artifact` header of `$1` with `version`/`revision`/
   `last_writer`.
3. Events: none — the workspace produces no session events
   (they live in project timelogs).
4. Resolution by title; mutation only via MCP handlers.

## 5. References

- `cerebro-canon.md` — the mother canon (GRADIENT-12)
- `migracion.md` G-6 — physical application of this layout
- `artefactos.md` §2.1 — level-3 workspace card

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
