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

# Canon — `identities/<agent>.cortex` (Level 1 / IDENTITY)

*English translation — canonical source: `docs/es/especificacion/identidad-canon.md`*

**Status:** current canon (ALFRED · CYCLE-16 · 2026-11-15, audited
by Heimdall).
**Scope:** `<workspace>/.arqux/identities/*.cortex` — an agent's
behavioral contract.

---

## 1. What it is

An agent's **behavioral contract**: who it is, which axioms govern
its behavior, which limits it does not cross, how it describes
itself. It is NOT memory: it accumulates no history or lessons —
only the current contract.

| Property | Value |
|---|---|
| Level | 1 |
| Read | `identity.get` / `identity.switch` — **always via handler** |
| Mutation | the contract is seeded by template (`workspace.init`/`protocol.adopt` registers only in the registry, not this file — `agents.cortex` retired: the last residue, holding only a `IDN:new-agent` leaked from a pathless test, was archived 2026-11-15) and mutates via `identity.elevate` **supervised** + Architect. **`protocol.register` does not exist** |

## 2. Canonical layout — two real variants

| # | Title | Sigils | Variant A (5/7) | Variant B (2/7: heimdall, seshat) |
|---|---|---|---|---|
| $0 | `GLOSSARY` | `$0:format` + `*_contract` | ✓ | ✓ |
| $1 | `IDENTITY` | `ARQX:artifact{level:1}` + `IDN:<agent>` | ✓ | ✓ |
| $2 | `AXIOMS` | behavioral `AXM:*` | ✓ | ✓ |
| $3 | `LIMITS` | `LIM:*` | ✓ | ✓ |
| $4 | `DESCRIPTION` | `DESC:*` | ✓ | — |
| $4 | `EXPERTISE` | `KNW:*` domains | — | ✓ |
| $5 | `DESCRIPTION` | `DESC:*` | — | ✓ |

### $0 GLOSSARY

- **`$0:format` must be the first line** — 6/7 files emit a
  declaration (`ARQX:arqx_contract`) **before** the format (drift to
  homologate; dialect detection demands it early).
- **`_contract` naming is dominant** (6/7 files); the drift is
  `alfred.cortex` — it uses the short form (`ARQX:arqx`, `IDN:idn`,
  `AXM:axm`, `LIM:lim`, `DESC:desc`) for **all** its sigils.
- Two glossary families: "ARQUX **AGENT** IDENTITY GLOSSARY"
  (named agents: alfred, heimdall, jarvis, seshat) vs "ARQUX
  **ROLE** IDENTITY GLOSSARY" (roles: auditor, executor, governor —
  `IDN` without `master`, `name` = role).

### $1 IDENTITY

`ARQX:artifact{level:1, name, usage:"identity", kind:"native"}` as the
first entry (transversal rule `formato.md`), followed by
`IDN:<agent>{name, role/group, purpose, master?, version, status}`.
Heimdall also carries `edit:false` (permission attribute in the
descriptor).

### $2/$3 — elevated behavior

`AXM:*`/`LIM:*` — only grows by **elevation from the router**
(aprendizaje.md §6): behavioral + transversal, always `propose` +
human confirmation. Real example: `AXM:verify_post_write_state` with
`source_lesson` + `evidence_ref:"brain:$8/LNG:…"` (alfred:51).

### $4 EXPERTISE (variant B)

`KNW:*{name, topic, content, dominio, status}` — expertise domains
(security_vigilance, forensic_audit…). Note: `dominio`
duplicates `content` in heimdall/seshat — known redundancy.

### $4/$5 DESCRIPTION

`DESC:<agent|persona|role>{name, body}` — purpose in prose; the
name varies (`persona` in alfred/jarvis, `role` in role-files).
`ROLE:*` declared in old versions of the canon **does not exist**.

## 3. Rules

1. **Contract, not storage** — `BEHAVIORAL LESSONS` deprecated;
   lessons live in brain `$8`.
2. **Always read via handler** — never direct reading.
3. **Every agent/subagent carries a contract** — injected at launch.
4. **Heimdall is read-only by contract** — `LIM:no_mutation` +
   `AXM:read_only_by_default` + `edit:false`.
5. **Elevation demands a human** — no `AXM`/`LIM`/`KNW` is added
   automatically.

## 4. References

- `cerebro-canon.md` §3 — brain sections (elevation origin)
- `aprendizaje.md` §2 — the nature×scope router (+§6.4 modes)
- `artefactos.md` §2.2 — level-1 card

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
