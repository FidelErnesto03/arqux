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

# `.cortex` format — transversal physical rules

*English translation — canonical source: `docs/es/especificacion/formato.md`*

**Status:** current canon (ALFRED · CYCLE-16 · 2026-11-15).
**Scope:** EVERY `.cortex` artifact in the framework — not just brains.
The complete artifact enumeration lives in `artefactos.md`; the brain
section canon in `cerebro-canon.md`.

---

## 1. What a `.cortex` is

A CODEC-CORTEX document: plain text, `$N` sections numbered
sequentially from `$0`, `SIGIL:name{attrs}` entries per line.
No executables, no binary format — memory readable by machine and
human.

| Level | Artifacts | Role |
|---|---|---|
| **0** | `timelog/SESNNN_*.cortex`, `issues/*.cortex`, `contexts/exec-*.cortex` | episodic / per-file record |
| **1** | `identities/<agent>.cortex` | agent behavioral contract |
| **2** | `skills/*.skill.md`, `cycles/**` (task/cycle), `learn-policies.cortex` | capability / config / work unit |
| **3** | `brain.cortex`, `meta-brain.cortex` | project / workspace memory |

## 2. Mandatory physical structure

```
$0:format{cortex:1.0, encoding:UTF-8}
SIGIL:name{type:"<type>", weight:"<B|M|H>", focus:"<layer>",
           fields:"...", desc:"...", open:true|false}
   ... executable declarations in $0 ...

$1: TITLE
ARQX:artifact{level:N, name:"...", usage:"...", kind:"...",
              version:"...", revision:"...", last_writer:"..."}
SIGIL:entry{...}
```

- **`$0` = pure declaration space.** `$0:format` opens; the
  executable declarations declare every emitted sigil. Hard rule:
  G016 requires `type:` on every `$0` symbol — that is why `$0`
  cannot hold data records. **Dominant real drift**: most artifacts
  emitted by current writers (6/7 identities, cycle tasks, templates,
  handoffs) carry the `*_contract` declarations **before** the
  `$0:format` — the format is only "first" in the strict minority;
  to be homologated.
- **`ARQX:artifact` = first body entry** (`$1`, before the document's
  first datum): the document declares itself at the point closest
  to `$0` the format allows. It carries the revision
  (`version`/`revision`/`last_writer` — `TLG:identity` pattern).
  **Real exceptions**: timelog writers emit `TLG:identity` before
  the `ARQX`; `learn-policies.cortex` and `.skill.md` do not carry
  it. (In `.cortex` issues the `$0` `ARQX` is the sigil *declaration*;
  the *record* is indeed first in `$1`.)
- **Legacy positions (read-only):** `$0.1`, titled `$15`, `$19` —
  accepted on read. **Audit correction**: `$19` is STILL emitted
  today — confirmed emitters (non-exhaustive list): `formats.py`,
  `writer.py`, `migrator.py`, `skill_store.py`, `session.py`,
  `protocol.py`, `_migrate.py`, `crud.py`, `entries.py`,
  `_lesson.py`, `_brain.py`, templates. The "never emitted" goal is
  the destination, not reality; readers keep resolving it by
  position.

## 3. Executable declarations

Every sigil emitted in the body MUST be declared in `$0`:

```
AUD:audit{type:"attrs", weight:"B", fields:"value:any?",
          focus:"Episodic", desc:"...", open:true}
```

The writer generates them automatically; a hand-rolled writer must
replicate them. Canonical nomenclature: `SIGIL:<sigil>_contract` for
the contract declaration — 6/7 identities use it; only
`alfred.cortex` carries the short form `ARQX:arqx` (old generation —
cosmetic drift to be homologated).

## 4. Strict vs tolerant

- **Strict:** `$0:format` + declarations + `ARQX` + level rules
  (E024/E034 in brain: active `FCS`/`OBJ`). It is the **goal** — the
  real corpus is mostly tolerant: 21/21 timelogs without
  `$0:format`, no skill declares it, issues with heterogeneous
  layouts. Not every new writer emits strict today.
- **Tolerant:** legacy parseable form without declarations — valid
  as append-only historical record. Not rewritten for cosmetics;
  homologated on the next legitimate write.
- **Short truth:** no handler returns `ok` before validating what it
  wrote; malformed → abort + revert (`AXM:silent_corruption`).

## 5. Writer contract

Every new write: (a) declares (`$0:format` + sigils), (b) carries
`ARQX:artifact` at the head of `$1`, (c) coalesces `$0.1`/`$19` →
canonical position, (d) preserves existing comments/titles,
(e) verifies post-write before returning `ok`.

## 6. References

- `niveles-cortex-arqux.md` — levels model
- `docs/en/explicacion/frontera-codec.md` — ArqUX/CODEC boundary
- `artefactos.md` — complete artifact census

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
