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

# Code ↔ canon conformance — review matrix

*English translation — canonical source: `docs/es/especificacion/conformidad.md`*

**Purpose:** instrument to direct the review of what the code
**does today** (actual) against what the `docs/es/especificacion/`
canon **demands** (real). Each row: component · current behavior with
evidence · canon requirement · gap · verification.

**Live corpus already migrated** (G-8, 2026-11-15): brain GRADIENT-12,
meta-brain canon+REGISTRY, 4 absorbed files removed.
This matrix covers the **software** — what keeps emitting/reading
the old model.

---

## A. Brain section structure

| Component | Current (evidence) | Canon demands | Gap |
|---|---|---|---|
| `constants.py` `BrainSection`/`BRAIN_SECTION_TITLES` | enum and map = GRADIENT-12 (`$0..$10`); `ALL_BRAIN_SECTIONS` keeps the 16 names for read-compat | GRADIENT-12 (`cerebro-canon.md` §2) | **resolved** (CYCLE-16) |
| `learning/sections.py` | `_TITLE_FOR_SIGIL` + `section_for_sigil()` resolve by title against the live doc | — | **partially conformant**: positional fallbacks remain — `_ID_FOR_SIGIL` (`BrainSection` fallback when the doc lacks the title), `section_title()` (:86-92), `plan.py` `$7` fallback |
| `brain_structure.py` (validator) | validates GRADIENT-12 by canonical id↔title | validates GRADIENT-12 + `ARQX:artifact` in `$1` | **resolved** (CYCLE-16) — fixtures updated to the 11-section layout |
| `templates/brain.cortex` / `meta-brain.cortex` | GRADIENT-12 templates emitted | GRADIENT-12 template | **resolved** (CYCLE-16) |
| `formats.py` `brain_from_model` | emits GRADIENT-12 (`ARQX`+concurrency in `$1`, legacy sections as titled appendices only when they carry content) | emits canon | **resolved** (CYCLE-16) |
| `skill.install` registry | `SKL` → `SKILLS` section (`KNOWLEDGE` fallback) by title | never positional | **resolved** — was `$6` (=canonical OBJECTIVES) |
| `loops.py` `loop_register` | `LOOP` → `LOOPS` by title, `$9` fallback | never positional | **resolved** — was legacy `$14` |
| `learning.record` | `LNG` → `LESSONS` by title, `$8` fallback + `section_title` | never positional | **resolved** — was bare `$8` |
| `project.py` seed instructions | prompt teaches the agent GRADIENT-12 | canon | **resolved** — taught the 15-section layout |

## B. Events (PULSE → timelog `$5 EVENTS`)

| Component | Current | Canon demands | Gap |
|---|---|---|---|
| `pulse.py` `record_pulse`/`append_pulse_to_brain` | appends `AUD` to timelog `$5 EVENTS` when `ses_ref` exists; brain-PULSE fallback by title (never positional `$7`) | append to the session's timelog `$5 EVENTS` | **resolved** (CYCLE-16) |
| ~14+ emitters (`record_pulse` callers: `handlers/skill.py`, `cycle.py`, `blueprint/*`, `issue.py`, `identity/switch.py`…) | write via `record_pulse` — same sink, destination resolved | write to timelog via `ses_ref` | **resolved** — callers passing `ses_ref` land in timelog |
| `blueprint/_helpers._record_to_brain` | routed by `record_pulse` | unified | **resolved** — looked up PULSE with `sec.id=="$7"` (collision with canonical ACTIVE_CONTEXT) |
| `next_pulse_event_id` | `SESNNN-EXXXX` with `ses_ref`; global `E-XXXX` only session-less (compat) | per-session `SESNNN-EXXXX` | **resolved** (CYCLE-16) |
| `timelog_store.py` | `$0..$5` + `append_event` + `AUD`/`DEC`/`ERR` declarations | `+ $5 EVENTS` | **resolved** |
| `evidence.list` / dashboard / session counters | `read_pulse_from_brain` merges legacy brain-PULSE + timelog EVENTS | read timelog(s) | **resolved** (unified reader) |
| T1: `PULSE_*`, `session.pulse.gc`, `LNG:pulse_sweep`, `pulse density` signal | auto-sweep out of the write-path; `_prune_timelog_events` = no-op (timelog never pruned); explicit `sweep`/`compact` act only on legacy brain-PULSE | retired — events never pruned | **resolved** — effective retirement over the canonical corpus; explicit pruning remains as legacy-residue maintenance |
| `session.close` | counts `pulse_events` via `read_pulse_from_brain` — unified reader (timelog `$5 EVENTS` + legacy brain-PULSE); the portable SES is written to `SESSIONS` by title | reports the own timelog's events | **resolved** — unified source, T1 descriptions retired (CYCLE-16) |

## C. Removed artifacts — orphan readers

| Component | Current | Canon demands | Gap |
|---|---|---|---|
| `_project.py` `find_project_root` | cascade: `contexts/exec-*.cortex` → **meta-brain `WRK:current.project_root`** → `context.cortex` (read-compat); `find_write_project_root` excludes both shared slots | fallback to meta-brain `$7` (`WRK:current.project_root`) | **resolved** (G-9, CYCLE-16) |
| `session.context.set` / `session.context.get` | writes exec-context + meta-brain `WRK:current`; reads exec-context → `context.cortex` (only if it is the chosen slot) → meta-brain | writes/reads meta-brain `$7` | **resolved** — `_write_context` without slug no longer recreates `context.cortex` |
| `session.handoff` + bootstrap consumers | write `HND:<to>` in brain `ACTIVE_CONTEXT` by title | `HND:<to>` in brain `$7`; claim = consumes the entry | **resolved** — `handoffs/` not recreated; the 5 migrated `HND` remain orphan residue |
| `session.bootstrap` | reads context via `context_get` (exec → meta-brain) | reads meta-brain | **resolved** |
| `sync.py` → meta-brain | resolves `ACTIVE_CONTEXT`/`FOCUS`/`KNOWLEDGE`/`REGISTRY` by title (`REGISTRY`→`PROJECTS`→`DOMAINS` legacy) | write by title | **resolved** — was CRITICAL ACTIVE COLLISION |
| `agents.cortex` consumers (`protocol.py` adopt/onboard/release/pause/resume, `project.py`, `workspace.py`) | write `IDN:*` in meta-brain `REGISTRY`; `write_projects_index` retired from `init_workspace` | read/write meta-brain `$10 REGISTRY` | **resolved** |
| `cortex_out.py` `format_status` | counts `DOM` in meta-brain `REGISTRY` (`PROJECTS`/`DOMAINS` fallback) | reads meta-brain `$10` | **resolved** |
| `learn-policies.cortex` loader (`core/learning/_common.py:29-34`) | `_resolve_policy_path` **already prefers project** and falls to packaged template `src/arqux/templates/` — never ws | one per project | **resolved** — document the silent template-fallback (package policy applies if the project's is missing: implicit decision to review) |

## D. ARQX metadata (`$15`/`$19` → `$1` header)

| Component | Current | Canon demands | Gap |
|---|---|---|---|
| `migrator.migrate_file` | injects `ARQX:artifact` inside `IDENTITY` when it exists; `$19` only for identity-less artifacts (tasks, cycles, manifest) | `$1` for brains/identities | **resolved** (CYCLE-16) |
| `brain_from_model` | `ARQX:artifact{...version,last_writer,updated}` in `$1 IDENTITY` — concurrency folded | `$1` | **resolved** (CYCLE-16) |
| remaining `$19` emitters (`_add_arqux_meta_section` for manifest/projects/task/cycle, `_migrate.py` rescue, writer `$0.1`→`$19`) | deliberate out-of-band for `IDENTITY`-less artifacts; the writer preserves existing structure | `$19` allowed outside brains | **conformant by design** — canon restricts `$1` to brains/identities |
| `sessions.py` version bump | `crud_update` on `$1/ARQX:artifact` with legacy `ERR:concurrency` fallback | `$1` | **resolved** |
| `read_arqux_metadata` | `_ARQUX_META_PRIORITY` favors `$1` over `$15`/`$19` by sigil | — | **resolved** |

## E. Writing/identity

| Component | Current | Canon demands | Gap |
|---|---|---|---|
| `identity.switch` | registers `HND` in `ACTIVE_CONTEXT` + event via `record_pulse` | handoff-event → timelog `$5`; no PULSE | **resolved** |
| `protocol.adopt`/`protocol.onboard`/`release` | writes `IDN:*` in meta-brain `REGISTRY` | writes meta-brain `$10 REGISTRY` | **resolved** |
| `identity.record`/`identity.elevate` | `LNG`→`LESSONS` by title + candidate nudge | unchanged (already conformant) | **resolved** |

## F. Verified residue in live corpus

| Item | Evidence | Action |
|---|---|---|
| `LOOP:vamos-ah` unparseable (E017) | hyphenated name off-grammar — renamed `vamos_ah` + `phases` compacted; `add_entry` now sanitizes names to `[A-Za-z0-9_]` | fix name + sanitize in writer | **resolved** |
| `SES:heimdall`/`SES:alfred` `status:"active"` | normalized to `current` (CYCLE-16); current writer emits no `status` | normalize to `current` | **resolved** |
| Brain `$0` WITHOUT declarations | populated with 13 `SIGIL:*_contract` contracts + `$0:format` (CYCLE-16); remaining `I001` are inherent codec noise (the meta-brain emits them too) | declare sigils in glossary (G-4) | **resolved** |
| `LNG:________*` placeholders **×183** | **resolved** — renamed deriving the name from the body (Architect approved, CYCLE-16). Historical residue, not an active bug: the writer (`_derive_lesson_name`, `handlers/cortex/learning.py:65-98`) already does `lstrip(" -\"")` before deriving. 212 total `LNG` in `$8` |
| `LNG:session_*` boilerplate ×22 | **drained** — census-lessons from `compact_session_pulse` (`pulse.py`, `lng_name=f"session_{ses}"`) removed by Architect decision (CYCLE-16). The generator stays alive for future explicit compacts |
| `SES` count = **24** total | 24 in `$10` — squatter moved (CYCLE-16) | move squatter to `$10` (G-4) | **resolved** |
| Off-canon drift: `DEC`/`LNG` in FOCUS, `SES` in KNOWLEDGE | 6 `LNG`→`$8`, 1 `SES`→`$10`, **6 `DEC`→`$2 AXIOMS`** (foundational pre-timelog decisions — Architect approved) | re-section (G-4) | **resolved** |
| Orphan `AUD:E_0001` in brain `$7` | written by old MCP server positional writer; migrated to `SES021` timelog `$5 EVENTS` with `migrated_from` attr (CYCLE-16) | relocate to timelog | **resolved** |

## G. Per-row verification protocol

For each touched row:

1. **Before**: `grep` current behavior + pin-down test if missing.
2. **Change**: implement canon destination; read-compat by title, never
   by number.
3. **After**: `cortex_verify` on affected artifact → `valid=true`;
   suite delta 0; `AUD` evidence in timelog `$5` (post-G-3b) or brain
   until reroute.
4. **Row closure**: mark ✓ with commit SHA.

## H. Proposed execution order

```
G-9  (orphan readers)     ← critical: the fallback is already broken
G-2  (constants/maps)     ← a single structural source of truth
G-3  (validator/template/builders + metadata $1)
G-3b ($5 EVENTS + emitter reroute + T1 retirement)
G-4  (residual brain drift)
G-5  (learning engine — spec aprendizaje.md §5)
G-7  (OBJ:_ post-restart)
```

Transversal plan rule: **new writers only emit canonical
positions; readers resolve by title and tolerate whatever legacy
positions remain** (`$15`/`$19`/archived-PULSE).

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
