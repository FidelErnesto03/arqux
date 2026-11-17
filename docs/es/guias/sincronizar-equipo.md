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
<p align="center"><sub>Guía · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Sincronizar políticas en equipo

Cuando varios workspaces (personas o agentes) comparten políticas, el **journal autoritativo** las ordena en una sola versión de la verdad. Dos comandos, un ritual.

> **Honestidad arquitectónica:** el journal es un **archivo canónico** (`<workspace>/.arqux/journal/journal.cortex`). ArqUX ordena los deltas; el **transporte lo decide tu equipo** — git, disco compartido, lo que sea. En v1 no hay servicio de sync propio ni replicación automática.

## Modelo mental

```text
                 journal.cortex (única autoridad, version:N)
                  ▲        ▲
        push-delta│        │pull-policy
                  │        │
        ┌─────────┴──┐  ┌──┴─────────┐
        │ workspace A │  │ workspace B │
        └────────────┘  └────────────┘
```

- El journal vive en **un** workspace raíz — el que el equipo designa como autoridad.
- Cada `push-delta` empaqueta reglas (entradas `RUL:`/`POL:`/`GTE:` de un `.cortex`) y las aplica **solo si** tu `--base` coincide con la versión actual del journal — bloqueo optimista.
- `pull-policy` imprime la sección `$3 POLICY` autoritativa: lo que el journal manda hoy.
- Resolución determinista: los deltas se aplican en orden de journal; dentro de una versión, una regla con el mismo nombre es reemplazada por el delta posterior.

## El ritual diario

```bash
# Al empezar — trae lo que el equipo consolidó
arqux pull-policy --path /ruta/al/journal

# Trabajas, cambias políticas en tu .cortex local…

# Al terminar — publica tu delta sobre la versión que viste
arqux push-delta --workspace mi-id --delta mi-delta.cortex --base N --path /ruta/al/journal
```

Un delta es un `.cortex` con las reglas que añades o actualizas:

```cortex
$0
$0:format{cortex:1.0, encoding:UTF-8}
RUL:no_secret_commit{name:"no_secret_commit", on:"*", check:"secret_pattern", when:"pre", enforce:"CODE"}
```

## El conflicto — ejemplo real

Dos writers sobre la misma base. A publica primero; B trabajaba sobre la base vieja:

```bash
$ arqux push-delta --workspace ws-a --delta delta-a.cortex --base 0 --path /journal
applied delta from ws-a: version=1 rules=1

$ arqux push-delta --workspace ws-b --delta delta-b.cortex --base 0 --path /journal
ERR_CONFLICT_VERSION: journal is at version 1, delta claims base 0 — human triage required
# exit 1 — nada se aplicó, nada se corrompió
```

**Resolución en 3 pasos:**

```bash
# 1. B trae el head actual — ve qué ganó
$ arqux pull-policy --path /journal
# journal policy — version 1
RUL:no_secret_commit{...}

# 2. B re-basea su delta sobre la versión actual
$ arqux push-delta --workspace ws-b --delta delta-b.cortex --base 1 --path /journal
applied delta from ws-b: version=2 rules=1

# 3. Ambas reglas ya conviven ordenadas
$ arqux pull-policy --path /journal
# journal policy — version 2
RUL:no_secret_commit{...}
RUL:require_evidence{...}
```

El conflicto no es un error del sistema — es el sistema **protegiendo** una escritura ciega. Si el delta de B pisa una regla que A acaba de tocar, el humano triagea.

## Topologías y garantías

| Topología | Cómo | Garantía |
|---|---|---|
| **Archivo compartido** | journal en disco accesible a todos (NFS/mount) | Orden total, bloqueo optimista |
| **Git-sync** | journal versionado en git; cada workspace hace pull/commit/push del repo journal | Igual + historial, pero el transporte git decide la disponibilidad |
| **Servicio futuro** | — | No existe en v1 — no está en la hoja, no se promete |

**Límites v1 (honestos):** sin transporte propio, sin merge automático semántico, sin auth sobre el journal — la autoridad del archivo la gobierna tu infraestructura de acceso. La firma Ed25519 de políticas es una capa adicional (ver [guía de evidencia](evidencia-y-cumplimiento.md)).

## Cheatsheet

| Quiero | Comando |
|---|---|
| Ver la política autoritativa | `arqux pull-policy --path <journal>` |
| Publicar mis reglas | `arqux push-delta --workspace <id> --delta <f> --base <N>` |
| Saber mi base correcta | `pull-policy` muestra `version` en su cabecera |
| Resolver conflicto | pull → re-push con `--base` actual → verificar |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
