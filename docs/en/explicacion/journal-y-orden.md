---
doc_type: explanation
status: informative
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
<p align="center"><sub>Explanation · Informative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Why the journal exists and how it orders

*English translation — canonical source: `docs/es/explicacion/journal-y-orden.md`*

> The *how to use it* lives in [team sync](../guias/sincronizar-equipo.md). This doc is the *why* it is designed this way.

## The problem it solves

When N workspaces write policies, each holds its own local truth. Without a single authority, "the current policy" depends on whom you ask — and two concurrent writers can stomp each other without noticing.

The authoritative journal (REQ-13) introduces a simple design decision: **one ordered sequence**. `journal.cortex` is append-ordered — deltas apply in arrival order, and the version is a monotone integer. No semantic merge, no history trees: a single line.

## Optimistic locking

`push-delta --base N` declares "my delta assumes the journal is at version N". If the journal is already at N+k, another writer won — and applying the delta blindly would produce a state the emitter never saw. That is why the system answers `ERR_CONFLICT_VERSION` and applies nothing.

It is optimistic because it **does not lock up front**: anyone can read and prepare a delta; only the stale writer trips at the door. The conflict cost is paid by the latecomer — re-read the head and re-base — not by whoever arrived first.

## Deterministic resolution

Within one version, if two deltas carry a rule with the same name, **the last one wins**. Deterministic, predictable, no heuristics: journal order is the only thing that matters. This turns consolidated policy into a pure function of the delta history — reproducible by anyone who replays the journal.

## Why a file, not a service (v1)

The journal is a `.cortex` file in a designated workspace, not a network service. It is an honest scoping decision:

- The **semantics** (total order, optimistic locking, determinism) are cheap to guarantee over a file — no distributed consensus needed.
- The **transport** (how the file reaches everyone) is the team's problem, not the format's: git, shared disk, manual copy. ArqUX does not opine.

Separating semantics from transport keeps the journal verifiable with `sha256sum` — the authority is a hash, not an API.

## Relationship with the rest of the system

- The **cycle seal** (REQ-03) seals artifacts of *one* project; the journal orders policies *across* workspaces.
- The **Ed25519 signature** (REQ-12) adds non-repudiation over deltas — who signed, not just what order.
- `pull-policy` is the read face: it translates the journal's `$3 POLICY` section into what an agent consumes.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
