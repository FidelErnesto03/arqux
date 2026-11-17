---
doc_type: guide
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
<p align="center"><sub>Guide · Normative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Synchronizing policies across a team

*English translation — canonical source: `docs/es/guias/sincronizar-equipo.md`*

When several workspaces (people or agents) share policies, the **authoritative journal** orders them into a single version of truth. Two commands, one ritual.

> **Architectural honesty:** the journal is a **canonical file** (`<workspace>/.arqux/journal/journal.cortex`). ArqUX orders the deltas; **transport is your team's choice** — git, shared disk, whatever. In v1 there is no built-in sync service or automatic replication.

## Mental model

```text
                 journal.cortex (sole authority, version:N)
                  ▲        ▲
        push-delta│        │pull-policy
                  │        │
        ┌─────────┴──┐  ┌──┴─────────┐
        │ workspace A │  │ workspace B │
        └────────────┘  └────────────┘
```

- The journal lives in **one** root workspace — whichever the team designates as the authority.
- Each `push-delta` packages rules (`RUL:`/`POL:`/`GTE:` entries from a `.cortex`) and applies them **only if** your `--base` matches the journal's current version — optimistic locking.
- `pull-policy` prints the authoritative `$3 POLICY` section: what the journal mandates today.
- Deterministic resolution: deltas apply in journal order; within one version, a rule with the same name is replaced by the later delta.

## The daily ritual

```bash
# At start — pull what the team consolidated
arqux pull-policy --path /path/to/journal

# You work, change policies in your local .cortex…

# At the end — publish your delta on top of the version you saw
arqux push-delta --workspace my-id --delta my-delta.cortex --base N --path /path/to/journal
```

A delta is a `.cortex` with the rules you add or update:

```cortex
$0
$0:format{cortex:1.0, encoding:UTF-8}
RUL:no_secret_commit{name:"no_secret_commit", on:"*", check:"secret_pattern", when:"pre", enforce:"CODE"}
```

## The conflict — real example

Two writers on the same base. A publishes first; B was working on the old base:

```bash
$ arqux push-delta --workspace ws-a --delta delta-a.cortex --base 0 --path /journal
applied delta from ws-a: version=1 rules=1

$ arqux push-delta --workspace ws-b --delta delta-b.cortex --base 0 --path /journal
ERR_CONFLICT_VERSION: journal is at version 1, delta claims base 0 — human triage required
# exit 1 — nothing applied, nothing corrupted
```

**Resolution in 3 steps:**

```bash
# 1. B pulls the current head — sees what won
$ arqux pull-policy --path /journal
# journal policy — version 1
RUL:no_secret_commit{...}

# 2. B re-bases their delta onto the current version
$ arqux push-delta --workspace ws-b --delta delta-b.cortex --base 1 --path /journal
applied delta from ws-b: version=2 rules=1

# 3. Both rules now coexist, ordered
$ arqux pull-policy --path /journal
# journal policy — version 2
RUL:no_secret_commit{...}
RUL:require_evidence{...}
```

The conflict is not a system error — it is the system **protecting** against a blind write. If B's delta stomps a rule A just touched, the human triages.

## Topologies and guarantees

| Topology | How | Guarantee |
|---|---|---|
| **Shared file** | journal on a disk reachable by all (NFS/mount) | Total order, optimistic locking |
| **Git-sync** | journal versioned in git; each workspace pulls/commits/pushes the journal repo | Same + history, but git transport decides availability |
| **Future service** | — | Does not exist in v1 — not on the roadmap, not promised |

**Honest v1 limits:** no built-in transport, no automatic semantic merge, no auth on the journal — the file's authority is governed by your access infrastructure. Ed25519 policy signing is an additional layer (see the [evidence guide](evidencia-y-cumplimiento.md)).

## Cheatsheet

| I want | Command |
|---|---|
| See the authoritative policy | `arqux pull-policy --path <journal>` |
| Publish my rules | `arqux push-delta --workspace <id> --delta <f> --base <N>` |
| Know my correct base | `pull-policy` shows `version` in its header |
| Resolve a conflict | pull → re-push with current `--base` → verify |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
