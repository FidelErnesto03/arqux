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

# Por qué existe el journal y cómo ordena

> El *cómo usarlo* vive en [sincronizar-equipo](../guias/sincronizar-equipo.md). Este doc es el *por qué* está diseñado así.

## El problema que resuelve

Cuando N workspaces escriben políticas, cada uno tiene su verdad local. Sin una autoridad única, "la política vigente" depende de a quién le preguntes — y dos writers concurrentes pueden pisarse sin darse cuenta.

El journal autoritativo (REQ-13) introduce una decisión de diseño simple: **una sola secuencia ordenada**. `journal.cortex` es append-ordered — los deltas se aplican en el orden en que llegan, y la versión es un entero monótono. No hay merge semántico, no hay árboles de historia: hay una línea.

## El bloqueo optimista

`push-delta --base N` declara "mi delta asume que el journal está en versión N". Si el journal ya está en N+k, otro writer ganó — y aplicar el delta ciegamente produciría un estado que el emisor nunca vio. Por eso el sistema responde `ERR_CONFLICT_VERSION` y no aplica nada.

Es optimista porque **no bloquea por adelantado**: cualquiera puede leer y preparar un delta; solo el escritor desfasado tropieza en la puerta. El costo del conflicto lo paga quien llega tarde — re-lee el head y re-basea — no quien llega primero.

## Resolución determinista

Dentro de una versión, si dos deltas traen una regla con el mismo nombre, **gana la última**. Determinista, predecible, sin heurística: el orden del journal es la única cosa que importa. Esto convierte la política consolidada en una función pura del historial de deltas — reproducible por cualquiera que replay el journal.

## Por qué archivo, no servicio (v1)

El journal es un archivo `.cortex` en un workspace designado, no un servicio de red. Es una decisión de alcance honesta:

- La **semántica** (orden total, bloqueo optimista, determinismo) es barata de garantizar sobre un archivo — no necesita consenso distribuido.
- El **transporte** (cómo llega el archivo a todos) es un problema del equipo, no del formato: git, disco compartido, copia manual. ArqUX no opina.

Separar semántica de transporte mantiene el journal verificable con `sha256sum` — la autoridad es un hash, no una API.

## Relación con el resto del sistema

- El **seal de ciclo** (REQ-03) sella artefactos de *un* proyecto; el journal ordena políticas *entre* workspaces.
- La **firma Ed25519** (REQ-12) añade no-repudio sobre los deltas — quién firmó, no solo qué orden.
- `pull-policy` es la cara de lectura: traduce la sección `$3 POLICY` del journal a lo que un agente consume.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
