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
<p align="center"><sub>Explicación · Informativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# `docs/es/explicacion/` — el por qué del sistema

Documentos Diátaxis tipo **explanation**: no enseñan a ejecutar (eso es `guias/`) ni especifican norma (eso es `especificacion/`) — explican decisiones y comportamiento.

## Índice

| Documento | Pregunta que responde |
|---|---|
| [`frontera-codec.md`](frontera-codec.md) | ¿Por qué existe una frontera ArqUX↔codec-cortex y qué cruza cada lado? |
| [`journal-y-orden.md`](journal-y-orden.md) | ¿Por qué el journal es la autoridad y cómo ordena los deltas? |
| [`casos-limite.md`](casos-limite.md) | ¿Qué hace el sistema en los 5 bordes: concurrencia, brain vacío, sintaxis inválida, handler/identidad ausentes? |
| [`sync.md`](sync.md) | ¿Cómo funciona internamente el módulo `arqux.sync` que mantiene el brain sincronizado? |
| [`test-suite-framework.md`](test-suite-framework.md) | ¿Cuál es la doctrina de la suite de tests? |

## Regla de clasificación

Si un doc enseña a **hacer** algo → va a `guias/`. Si declara lo que **es** normativo → `especificacion/` o `referencia/`. Si explica **por qué** → vive aquí.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
