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

# Event lifecycle — timelog `$5 EVENTS`

*English translation — canonical source: `docs/es/especificacion/eventos-timelog.md`*

**Status:** current canon (destination model) + historical T1
reference (ALFRED · CYCLE-16 · 2026-11-15).
**Folder:** `docs/es/especificacion/` — this document answers *"where
do events live and how do they flow?"*.

---

## 1. Event lifecycle — timelog `$5 EVENTS` (destination model)

**Principle:** an event (`AUD`/`DEC`/`ERR`) belongs to the session that
produced it. The brain is *inter*-session memory; the timelog is
*intra*-session memory. Under this canon, the `PULSE` section
disappears from the brain and each timelog gains one more section:

```
$0  timelog glossary (+ AUD/DEC/ERR declaration)
$1  IDENTITY    TLG:identity{project, ses, opened, version, revision}
$2  ACTIVITIES  ACT:*{start, end, state, ...}        (intervals — today)
$3  RECEIPTS    RCV:*                                (external projection)
$4  PROJECTIONS PRJ:*                                (per-provider marks — today)
$5  EVENTS      AUD:SES021-E0042{kind, event, ...}   (events — NEW;
                stored on disk as underscore E_NNNN — codec separator)
```

### 1.1 Emission

- Every handler calling `record_pulse()`/`evidence.record` emits the
  `AUD`/`DEC`/`ERR`/`LOOP` to `$5 EVENTS` of the active session's
  timelog. Most emitters **do not pass an explicit `ses_ref`**: since
  CYCLE-16 `record_pulse` auto-resolves it from the ambient
  execution/session (`_resolve_ses_ref` — `authoritative_execution_key()`
  + `current_session_ref()`); it only falls back to the brain's legacy
  PULSE when no session is bound.
- **Free concurrency:** each agent/session writes its own file with
  its own lock — the system's hottest write path stops competing for
  the brain lock.
- **Namespaced IDs:** `SESNNN-EXXXX` — per-session sequence, no
  global brain scan to increment. `E-XXXX` remains as compat when no
  `ses_ref` is resolvable.
- **Sigils admitted in `$5 EVENTS`:** `AUD`, `DEC`, `ERR`, `LOOP`
  (`timelog_store.EVENT_SIGILS`; `loops.log_event` routes its trail
  via `append_event` — never a raw append outside `$5`).

### 1.2 Durability and query

- **Append-only, never pruned.** Evidence becomes truly
  durable: today T1 silently trims it (`evidence.list` over old
  events already returns empty — the "durability" was fiction).
- **Per-session read** = read its timelog (active session, dashboard,
  forensics). **Cross-session read** (`evidence.list`, learning) =
  scan timelogs — enumerable by name/date, cacheable by `revision`.
- **Handoffs:** the event is noted in the *emitter's* timelog; the
  pending queue lives as `HND:<to>` in brain `$7` (cerebro-canon.md §3).

### 1.3 Effects on the brain

- `PULSE` ceases to exist as a section — the brain drops to **11
  sections** (`$0`–`$10`) and loses ~50% of its entries (276 of ~560).
- `WRK:current` (`$7`) remains the answer to "where was I"; the
  *how* events live in the session.
- T1/T2/T3 **are retired**: there is nothing left to prune in the
  brain. `LNG:pulse_sweep` and `session.pulse.gc` are deprecated with
  the migration.

### 1.4 Legacy — migrated in G-8

The brain's historical `AUD`s (**276** in `$7`, verified by
direct count — previous audits mistakenly cited 285) were
archived to `.arqux/archive/hygiene-2026-11-15/pulse-legacy.cortex`.
The canonical alternative (migration to their `ses_ref`'s timelog) was
discarded during the operation — the archive preserves the evidence
without forensic rewriting. Reading `PULSE` in old brains remains as
legacy-compat, like `$0.1`/`$15`/`$19` for metadata (`formato.md`).

**Closed warning (CYCLE-16)**: `pulse.py` now routes `AUD` to the
timelog `$5 EVENTS` when a `ses_ref` exists, and to the PULSE fallback
*by title* when not — never to positional `$7` (which under the new
layout is `ACTIVE_CONTEXT`).

### 1.5 T1 mechanism — RETIRED (CYCLE-16)

T1 was **removed from the write-path**: the auto-sweep no longer fires
on every `record_pulse`. Timelog `$5 EVENTS` events are append-only
and **never pruned** (`_prune_timelog_events` = deliberate no-op). The
explicit `sweep`/`compact` handlers survive only as best-effort
maintenance of the brain's legacy PULSE (pre-migration residue), and
`LNG:pulse_sweep` remains the census-lesson they emit. Doctor's
`pulse density` signal reports informational density, with no
automatic pruning.

---

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
