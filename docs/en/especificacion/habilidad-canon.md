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

# Canon — `skills/*.skill.md` (Level 2 / SKILL)

*English translation — canonical source: `docs/es/especificacion/habilidad-canon.md`*

**Status:** current canon (ALFRED · CYCLE-16 · 2026-11-15, audited
by Heimdall).
**Scope:** `<workspace>/.arqux/skills/` and `<project>/.arqux/skills/`
— framework capabilities (16 current skills).

---

## 1. What it is

A **capability**: procedure + contract of a functional domain.
Level 2 — between identity (who) and the brain (what the project knows).

## 2. The three real physical variants

| Variant | Basis | Real examples |
|---|---|---|
| **A — sigil envelope + prose body** | `$N` sections with entries + `## §` explanatory markdown | `comms`, `arqux-issues` |
| **B — YAML frontmatter** | `---` (`skill_id`, `name`, `version`, `status`, `kind`, `usage`, `layer`, `blp_ref`) + `§N` markdown with embedded entries | `blueprint-synthesize`, `voice` |
| **C — pure envelope** | entirely `$0`–`$N` sigiled, no prose | `cortex`(×2), `workflows`(×2), `autonomia`, `diagram`, `learning`, `protocol` |

**No `.skill.md` declares `$0:format`** (0/16) nor `ARQX:artifact`
— skills are tolerant by design: the envelope is what is governed,
the markdown body never strict-parses.

### Real executable sigils

Dominant: `AXM`, `STP`, `IDN`, `HDL`, `FMT`, `LOOP`. Minority:
`WK` (5 occurrences), `REG` (0). The markdown body is optional and its
position varies — in several skills the whole contract lives in sections.

### `skills/workflows/` — index+subdir pattern

`workflows.skill.md` is an index (`IDN:wN{file:"workflows/wNN-*.md"}`)
of flat `wNN-*.md` files (not `.skill.md`). Real divergences:
workspace carries 12 files (missing `w12` **and `w14`**), project 13
(missing `w03`); the index references `w00-triage.md` **nonexistent**
(both levels) and at project level also references dangling `w03` —
two broken references + unindexed `w12`/`w14` (data debt).

## 3. Rules

1. **One domain per skill** — no mega-skills.
2. **The executable goes in the envelope** — `AXM`/`STP`/`HDL`/`IDN`;
   prose explains, it does not execute.
3. **Discovery, not hardcoding** — match by task (`skill.list`,
   `skill.get`).
4. **External bridges apart** — external providers (Teamwork:
   `timelog-compliance`) live outside `.arqux/skills/`, on-request
   (`AXM:external_providers_decoupled`).
5. **Known tension**: `voice.skill.md` declares `layer: 3` in
   frontmatter — contradicts "level 2" if frontmatter rules
   (pending Architect).

## 4. Set asymmetry

ws (9 skills): autonomia, comms, voice extra. Project (7): includes
`arqux-issues` (the only project-level one — source of the issue format).

## 5. References

- `formato.md` — `.cortex` envelope vs markdown body, strict/tolerant
- `artefactos.md` §2.3 — level-2 card
- `gobernanza-canon.md` — `arqux-issues.skill.md`

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
