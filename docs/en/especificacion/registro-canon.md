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

# Canon — `learn-policies.cortex` (learning engine config)

*English translation — canonical source: `docs/es/especificacion/registro-canon.md`*

**Status:** current canon (ALFRED · CYCLE-16 · 2026-11-15, post-G-8,
audited by Heimdall).
**Scope:** `<project>/.arqux/learn-policies.cortex` — engine
configuration. **One per project** (Architect's decision).

---

## 1. What it is

**Not a registry nor memory: it is the learning engine's executable
configuration.** `POL` rules + `THR` thresholds + `PRT`/`KNW`
protections + `GTE` gates.

| Property | Value |
|---|---|
| Level | 2, `usage:"skill"` — executable configuration document |
| Location | `<project>/.arqux/` — per project (15+ live copies) |
| Mutation | **no governed handler today** — written by template at `project.init`/`workspace.init` (`handlers/project.py:66`, `workspace.py:101`); later mutation = debt (gap G-5, no `learn.policy.*` exists) |

## 2. Real layout (7 sections, verified)

| # | Title | Content |
|---|---|---|
| $0 | glossary | `$0:format` + 7 contracts (`ARQX`, `IDN`, `THR`, `POL`, `PRT`, `GTE`, `KNW`) |
| $1 | `IDENTITY` | `IDN:learn_policies{name, version, target, status}` — **data defect**: missing `ARQX:artifact` (the artifact carries no card of its own) |
| $2 | `SCORING` | `THR:golden_fibonacci` (threshold sequence) |
| $3 | `PROTECTED TARGETS` | `PRT:critical_sigils` (per-sigil protection) |
| $4 | `CANDIDATE-DRIVEN LEARNING` | `POL:candidate_detection`, `POL:candidate_elevation`… |
| $5 | `POLICY-DRIVEN LEARNING` | `POL:from→to{action, lift_when}` + the file's DSL note |
| $6 | `GATES` | `GTE:default_mutation`, `GTE:critical_mutation` |
| $7 | `CONFIGURABLE THRESHOLDS` | `KNW:*` — cooling, feedback, protected_patterns |

## 3. Operative semantics (verified against `plan_patch`)

- **Live fields** of `POL`: `from`, `to`, `action`.
- **Inert fields** (documentation, not evaluated): `source`, `target`,
  `lift_when`, `requires`, `when >=` — `lift_when` has zero
  consumers in `src/`; `requires:"admin_policy"` is **dead by
  non-modeling**: `plan.py:94` does `getattr(chosen, "requires")` but
  `PolicyEntry` (algorithms/policy.py) carries no such field — the
  `admin_confirmed` branch is unreachable (the file's own `$5` note,
  "requires: is not modeled", is **correct**).
- **Real DSL**: `when:` admits only `==, !=, in, not in, and, or, not`
  — `>=` and `|` are not expressible (any other token → fail-closed
  parse error, conditions.py).
- **`POL:block_ses_to_lng`** (`$5`): **ACTIVE and intentional**
  block installed 2026-11-15 — `aggregate_value()` produces boilerplate
  (`lesson:"closed"`); lift only when the aggregation issue closes.
  Not "stale": it is the gate protecting `$8` today.
- **Inert knobs** (`$7`): cooling/feedback/protected_patterns parse
  without effect on the detection path — reactivate
  (aprendizaje.md §6.6) or remove. Pending Architect.
- **Protection duality**: `PRT` protects by sigil (`$3`);
  `KNW:protected_patterns` by pattern (`$7`) — today `plan_patch` uses
  hardcoded `_PROTECTED_SIGILS` and ignores both (G-5 debt). The PRT
  key was `items:` (dead — `policy.py:190` reads
  `sigils|targets|protected`); corrected to `sigils:` in the ARQUX
  file (CYCLE-16) — still without a consumer until G-5.

## 4. Consolidation note (G-8)

The workspace's **state registries** are no longer files — they live
as meta-brain sections (`meta-cerebro-canon.md`):

| Former file | Destination |
|---|---|
| `agents.cortex` | meta-brain `$10 REGISTRY` (`IDN:*`) |
| `projects.cortex` | meta-brain `$10 REGISTRY` (`DOM:*`) |
| `context.cortex` | meta-brain `$7 ACTIVE_CONTEXT` (`WRK:current`) |
| `learn-policies.cortex` (workspace) | removed — one per project |

Rule: **an index the meta-brain already carries does not deserve its
own file**.

## 5. References

- `aprendizaje.md` — consumer; §4 current engine, §6 proposal
- `meta-cerebro-canon.md` — `$10 REGISTRY`
- `migracion.md` §1 — executed consolidation

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
