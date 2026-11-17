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

# `docs/en/explicacion/` — the why of the system

*English translation — canonical source: `docs/es/explicacion/README.md`*

Diátaxis **explanation** documents: they do not teach execution (that is `guias/`) nor declare norm (that is `especificacion/`) — they explain decisions and behavior.

## Index

| Document | Question it answers |
|---|---|
| [`frontera-codec.md`](frontera-codec.md) | Why does an ArqUX↔codec-cortex boundary exist and what crosses each side? |
| [`journal-y-orden.md`](journal-y-orden.md) | Why is the journal the authority and how does it order deltas? |
| [`casos-limite.md`](casos-limite.md) | What does the system do at the 5 edges: concurrency, empty brain, invalid syntax, missing handler/identity? |
| [`sync.md`](sync.md) | How does the `arqux.sync` module that keeps the brain synchronized work internally? |
| [`test-suite-framework.md`](test-suite-framework.md) | What is the doctrine of the test suite? |

## Classification rule

If a doc teaches how to **do** something → it goes to `guias/`. If it declares what is **normative** → `especificacion/` or `referencia/`. If it explains **why** → it lives here.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
