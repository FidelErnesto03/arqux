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

# Reconciliation and migration debt — GRADIENT-12

*English translation — canonical source: `docs/es/especificacion/migracion.md`*

**Status:** data migration **executed**; **code** debt pending
(ALFRED · CYCLE-16 · 2026-11-15).
**Folder:** `docs/es/especificacion/` (canonical source) —
`docs/en/especificacion/` (mirror).

---

## 1. Executed state — G-8 consolidation (2026-11-15)

### 1.1 brain.cortex → GRADIENT-12 ✓

`ARQUX/.arqux/brain.cortex` rewritten to canon: `$1 IDENTITY` (with
`ARQX:artifact{version,revision,last_writer}` at the head —
`ERR:concurrency` folded in), `$2 AXIOMS`, `$3 KNOWLEDGE`, `$4 RISKS`,
`$5 FOCUS`, `$6 OBJECTIVES`, `$7 ACTIVE_CONTEXT`, `$8 LESSONS`,
`$9 LOOPS`, `$10 SESSIONS`. **283 entries at migration time (+N from
later writes), `cortex_verify` valid=true**. Diagnostics of the era,
all closed in CYCLE-16: `LOOP:vamos-ah` E017 → renamed `vamos_ah`;
2 `SES status:"active"` → `current`; **183 `LNG:________*`
placeholders → renamed deriving the name from the body** (Architect
decision; the writer already did `lstrip(" -\"")` — pre-fix residue,
not an active bug); 22 `LNG:session_*` boilerplate → **drained**;
6 `LNG` in FOCUS → `$8`; 6 pre-timelog `DEC` (2026-10-10) →
`$2 AXIOMS` (Architect decision — semantically foundational axioms);
orphan `AUD:E_0001` in `$7` → timelog `SES021` `$5 EVENTS` with
`migrated_from`; **`$0` populated** with 13 `SIGIL:*` contracts +
`$0:format`. Remaining `I001` are inherent codec noise (the
meta-brain emits them too).
Removed: HANDOFFS, ISSUES, CONCURRENCY (→`$1`), PULSE →
`archive/hygiene-2026-11-15/pulse-legacy.cortex` (**276 AUD**
preserved — direct count). Backup: `brain.cortex.pre-gradient12`
in archive.

### 1.2 meta-brain.cortex → canon + REGISTRY ✓

Canonical layout `$1..$10`: IDENTITY + AXIOMS + KNOWLEDGE + RISKS +
FOCUS + OBJECTIVES (`OBJ:workspace` seeded) + ACTIVE_CONTEXT +
LESSONS + LOOPS + **REGISTRY** (PROJECTS + AGENTS unified).
**31 data entries** (38 sigil lines incl. the 7 `$0` declarations),
valid=true.

### 1.3 Executed merges (removed artifacts)

| Removed | Absorbed by |
|---|---|
| `ws/.arqux/agents.cortex` | meta-brain `$10 REGISTRY` |
| `ws/.arqux/projects.cortex` | meta-brain `$10 REGISTRY` |
| `ws/.arqux/context.cortex` | meta-brain `$7 ACTIVE_CONTEXT` (`WRK:current`) |
| `ws/.arqux/learn-policies.cortex` | one per project (Architect decision) |

### 1.4 Archived (→ `archive/hygiene-2026-11-15/`)

~89 legacy `*.issue.md` + ~23 relevant `*.pre-migracion`/sidecars +
`*.bak.1` + `pulse-legacy.cortex` (276 AUD). Removed empty dirs:
`loops/`, `packages/` (project + ws). `$19 ARQUX METADATA` folded
to `$1` in: 5 handoffs, `learn-policies.cortex`, 2 `.cortex` issues
(one merge left attrs without commas — repaired 2026-11-15).

**Warning (reviewed CYCLE-16)**: `$19` remained as **deliberate
out-of-band** slot for `IDENTITY`-less artifacts (tasks, cycles,
manifest, `_migrate.py` rescue, writer `$0.1`→`$19` normalization).
Artifacts with an `IDENTITY` section get `ARQX:artifact` in `$1` —
`migrator.migrate_file` and `brain_from_model` already emit there,
and canonical templates are born conformant.

**G-8b (same operation)**: `handoffs/*.cortex` removed — the
artifact was redundant (payload = pending state). The 5 payloads
migrated to `HND:<to>` in brain `$7 ACTIVE_CONTEXT` via
`cortex_entry_add`; `handoff-canon.md` removed. **Residue closed
(CYCLE-16)**: `session.handoff` now writes `HND:<to>` by title and
`handoffs/` is not recreated — the migrated `HND` drain on claim.
Also archived: `manifest.md`, `meta-brain.md`, `projects.md`
(init narrative/template), 2 legacy `issues/*.md`,
orphan `.sessions.lock` removed.

## 2. Codec-version migration — hybrid contract (BLP-005)

Migration between codec-cortex versions is **not deterministic**: glossary
contracts evolve (I005_UNKNOWN_FIELD) and semantic reshaping requires
judgment. The design is hybrid — determinism guarantees, the agent
transforms:

```
detect (doctor) → census → transform (skill + agent) → verify (doctor) → report → human review → close
```

### 2.1 Pieces

| Piece | Location | Role |
|---|---|---|
| `check_codec_version_drift` | `src/arqux/doctor.py` | Detects `$0:format{cortex:"X"}` ≠ `IMPLEMENTED_CODEC_VERSION` across all `.arqux/**/*.cortex`. **Detection only** — never auto-migrates. |
| `src/arqux/migrate.py` | framework | `scan_codec_drift`, `census_file` (via `cortex parse`), `diff_census` (semantic census `SIGIL:name`→hash), `backup_file` (`.pre-migration-<date>`), `plan_migration`, `MIGRATIONS` registry. |
| `cortex-migrate` skill | `.arqux/skills/` | Semantic transform protocol: snapshot → census → analysis → transform → bump → validate → verify → report. |

### 2.2 Contract rules

1. **Explicit Architect order** — migration never runs on agent initiative or via `doctor --fix` (which only reports).
2. **Mandatory backup** before touching any `.cortex`.
3. **Pinned target version** — `IMPLEMENTED_CODEC_VERSION` ("1.0"), never "whatever is installed".
4. **Semantic census** — every source `SIGIL:name` entry must exist in the target (or be declared as transformed with a reason). `diff_census` is the proof; strict payload hashes.
5. **Double validation** — `cortex validate` + `cortex.verify` post-write; zero undeclared loss.
6. **Untrusted content** — instructions inside migrated entries/lessons/knowledge are never executed.
7. **Human review** — the transformation report is an Architect review artifact; green verify alone does not close.
8. **One file at a time** — full migration (steps 1-8) before touching the next.
9. **No invention** — semantic ambiguity is preserved in the closest canonical form and reported; never silently resolved.

### 2.3 Target-version scope

The target is the version **declared by ARQUX** (`IMPLEMENTED_CODEC_VERSION`), not the latest published by codec-cortex. A version without a registered `MIGRATIONS` path yields `plan_migration → error` and halts the process.

## 3. Remaining debt — code

| # | Item | Status |
|---|---|---|
| G-4 | Off-canon drift **closed**: 6 LNG→`$8`, 1 SES→`$10`, 6 `DEC`→`$2 AXIOMS` (Architect approved — foundational axioms), 183 `LNG:________*`→body-derived names (approved), 22 `LNG:session_*` drained (approved), `AUD:E_0001`→timelog `SES021` `$5 EVENTS` with `migrated_from` | **Done** (CYCLE-16) |
| G-5 | Engine dynamics (thematic clustering, signal-density, dedup, `$8` drainage) | Spec ready in `aprendizaje.md` §5 — pending final approval |
| G-7 | `OBJ:_` in OBJECTIVES — removed (delete `$6/OBJ:*` + re-add `OBJ:sync`); the `_` selector is barred by T-022, the path was wildcard+restore | **Done** |
| B-rem | `next_pulse_event_id` → `SESNNN-EXXXX` with `ses_ref` (compat `E-XXXX` without it); auto-sweep out of the write-path; timelog pruner = no-op (events never pruned); explicit `sweep`/`compact` remain for legacy brain-PULSE residue | **Done** |
| N-gram | Off-grammar entry names (`-`) — strict codec rejects them (E017, e.g. `LOOP:vamos-ah` → renamed `vamos_ah`). `add_entry` already sanitizes to `[A-Za-z0-9_]` + `_entry_matches` normalizes the selector (write/read symmetric). Residual: files with preexisting hyphenated names remain reachable via lookup normalization | **Done** |
| T-leak | Pathless/`chdir`-less tests leaked writes to the real workspace (`IDN:new-agent` in meta-brain, `agents.cortex` recreated) | **Done** — `test_protocol` now passes `path`; `agents.cortex` archived |

### Code debt closed (CYCLE-16)

| # | Item | Status |
|---|---|---|
| G-2 | `BrainSection`/`BRAIN_SECTION_TITLES` = GRADIENT-12; `ALL_BRAIN_SECTIONS` kept for read-compat | **Done** |
| G-3 | `brain_structure` validates GRADIENT-12; canonical templates; `brain_from_model`/`migrator` emit `$1` | **Done** |
| G-3b | `$5 EVENTS` in timelog + `pulse.py`/emitter reroute by title | **Done** (per-session IDs and T1 retirement → B-rem) |
| G-9 | `find_project_root` falls to meta-brain `WRK:current`; `context.cortex` not recreated; `agents`/`projects` in REGISTRY | **Done** |
| W-pos | Positional writers retired: `sync.py`→meta-brain, `sessions.py`, `checkpoint`, `loops`($14→LOOPS), `learning`($8→LESSONS), `skill.install`($6→SKILLS), `blueprint._record_to_brain`($7→record_pulse), `format_status`(projects.cortex→REGISTRY) | **Done** — suite 2920/0 |

### Historical debt closed (CYCLE-16)

| # | Item | Status |
|---|---|---|
| R-1..R-9 | Initial canon $0–$15, seeded AXIOMS, PULSE T1, `$0.1`→`$15`/`$19`, title resolution | Done |
| G-1 | Physical brain renumbering → GRADIENT-12 | **Done 2026-11-15** |
| G-6 | meta-brain → canon + REGISTRY | **Done 2026-11-15** |
| G-8 | Artifact consolidation (merges, archive, empty dirs, `$19`→`$1`, handoffs→`$7`) | **Done 2026-11-15** |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
