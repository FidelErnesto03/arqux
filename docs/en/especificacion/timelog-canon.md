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

# Canon — `timelog/SESNNN_*.cortex` (session / episodic)

*English translation — canonical source: `docs/es/especificacion/timelog-canon.md`*

**Status:** current canon (ALFRED · CYCLE-16 · 2026-11-15, audited
by Heimdall).
**Scope:** `<project>/.arqux/timelog/` — one artifact per session.

---

## 1. What it is

The **intra-session artifact**: writes by default, never summarizes
(AXM-2). The session's append-only episodic memory — the source the
learning engine produces lessons from.

| Property | Value |
|---|---|
| Location | `<project>/.arqux/timelog/` — project only |
| Naming | `SESNNN_YYYYMMDD_HHMMSS.cortex` — **no agent mark** (21 current files) |
| Writer | `session.context.set`/`close`, `cortex.checkpoint` via `observe()` — **there is no `session.open`** |
| Operation | transient `*.lock` locks during writes (cleaned up on finish) |

## 2. Real layout (verified on corpus)

```
$0: <title>             title comment (pre-1.0 corpus: no
                        $0:format — the current serializer
                        timelog_store.py:54-79 DOES emit the full
                        dialect + 5 contracts on the next
                        rewrite)
$1: IDENTITY            TLG:identity{project, ses, opened,
                        version, revision}
$2: ACTIVITIES          ACT:*{start, end, state, revision,
                        last_activity?} — append-only
$3: RECEIPTS            RCV:* — empty in the corpus today
$4: PROJECTIONS         PRJ:* — empty in the corpus today
```

Real notes:

- **`$4` absent in 7 files** (SES002–012): the split follows the
  re-serialization date vs PRJ support (T-038, 2026-10-22) —
  not a single migration.
- **`$5 EVENTS` = destination model** (eventos-timelog.md): today AUD
  events go to the brain positional `$7` (= `ACTIVE_CONTEXT`
  post-GRADIENT — active collision); AUD→timelog reclassification is
  G-3b debt.
- **`last_activity` lives in `$2`** in the `ACT:*` entries of
  re-serialized files (server heartbeat, `timelog_store.py:175`),
  never in `TLG:identity`.
- The current serializer also inserts `ARQX:artifact{level:"0",
  name:"timelog"}` in `$1` (timelog_store.py:160) — corpus still
  without it.
- Event spelling: canonical ids `E-NNNN` (hyphen) stored as
  `E_NNNN` (underscore — hyphen is the codec's selector separator);
  the destination model prescribes `SESNNN-EXXXX` per session (G-3b).

## 3. Relationship with the brain (the division)

| Timelog (episodic) | Brain (semantic) |
|---|---|
| every step, unevaluated | what was extracted and evaluated |
| `ACT`/`RCV`/`PRJ` | `AUD`/$5, `DEC`, `LNG`… |
| lifetime = the session | lifetime = the project |
| `timelog.query` per session | `cortex.read` per section |

The session dies; the brain inherits only what deserves to persist
(`$10` → events `$5` → lessons `$8` → knowledge `$3`).

## 4. References

- `cerebro-canon.md` §1.2 — why the timelog does not live in the brain
- `eventos-timelog.md` — brain `AUD`/`DEC` → `$5` (destination model)
- `artefactos.md` §2.4 — level-0 card

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
