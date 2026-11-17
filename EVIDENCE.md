---
doc_type: report
status: normative
version: 1.0.0
verified: 2026-11-15
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="./docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Reporte · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Modelo de evidencia de ArqUX

Qué constituye evidencia en ArqUX 1.0.0, con qué campos reales, quién la escribe, quién la verifica y qué queda explícitamente fuera. Documento para auditor: cada afirmación es verificable contra el código o un artefacto generable.

## Qué es evidencia en ArqUX

La evidencia es el registro **append-only y tamper-evident** de las acciones del agente. Cada invocación de handler que muta estado produce una entrada: quién hizo qué, cuándo y sobre qué artefacto. Sirve a tres fines:

1. **Auditabilidad** — cualquier parte puede revisar qué pasó y por qué.
2. **Integridad verificable** — sello SHA-256 por archivo `.cortex`; alterar un byte rompe la verificación.
3. **Aprendizaje** — el motor de aprendizaje mina la evidencia para elevar patrones a lecciones.

## Catálogo de artefactos de evidencia

### 1. Timelog — `.arqux/timelog/SES<NNN>_<timestamp>.cortex`

Registro nativo de trabajo por sesión. Secciones reales:

| Sección | Sigilo | Campos reales |
|---|---|---|
| `$1 IDENTITY` | `TLG:identity` | `project`, `ses`, `opened` (ISO-8601 UTC), `version`, `revision` |
| `$2 ACTIVITIES` | `ACT:<nombre>` | `start`, `end`, `state` (open/closed), `last_activity`, `revision` |
| `$3 RECEIPTS` | `RCV:<nombre>` | Recibo de proyección externa |
| `$4 PROJECTIONS` | `PRJ:<nombre>` | Marca de proyección por proveedor |

Todo intervalo lleva timestamps ISO-8601 UTC y un contador `revision` que se incrementa en cada escritura.

### 2. Sello de ciclo — `seal.cortex`

`seal_sha256:"<hex>"` — hash SHA-256 del artefacto. **Verificación**: `arqux cortex-verify <archivo>` recomputa cada hash declarado y falla sobre cualquier divergencia.

### 3. Bundle de evidencia — `arqux evidence export`

Genera un `.cortex` consolidado con sigilo raíz `EVD` y eventos por tipo:

| Sigilo | Contenido |
|---|---|
| `ARQX` | Metadatos del artefacto |
| `SPN` | Span de ejecución (intervalo de sesión) |
| `AUD` | Evento de auditoría |
| `DEC` | Evento de decisión |
| `ERR` | Evento de error |
| `LOOP` | Evento de loop |

**Privacidad obligatoria**: el export escanea los timelogs por campos marcados `private`. Si encuentra alguno, **bloquea** con `PermissionError` salvo que se pase `--redact-private` (los elimina del bundle) o `--allow-raw` (los incluye, decisión explícita). No hay modo silencioso.

### 4. Firmas Ed25519 — REQ-12

Firma real (no opcional): `arqux policy sign <doc> <key>` añade una entrada `SIG:signature` al documento `.cortex`; `arqux policy verify <doc>` la valida. La firma cubre los bytes canónicos del documento **excluyendo** sus propias líneas `SIG:` — alterar cualquier otro atributo produce `ERR_INVALID_SIGNATURE`. `generate_keypair` genera el par de claves.

### 5. Journal — `journal.cortex` (REQ-13)

Registro autoritativo de sincronización multi-workspace: `JRN:journal{version, deltas, rules, updated}`. **Optimistic locking**: un push declara su `base_version`; si no iguala la versión actual del journal, el push es rechazado — la divergencia queda visible, nunca sobreescrita en silencio. `$3 POLICY` publica las reglas autoritativas (`pull_policy`).

## Cadena de custodia

| Artefacto | Escribe | Verifica |
|---|---|---|
| Timelog | Handlers de lifecycle por sesión | `arqux cortex-verify` + lectura de secciones |
| Sello | Handler al sellar ciclo | `arqux cortex-verify` (recomputa SHA-256) |
| Bundle | `arqux evidence export` | Diff campos↔timelogs + gate de privacidad |
| Firma | `arqux policy sign` (Ed25519) | `arqux policy verify` |
| Journal | `push_delta` con `base_version` | Rechazo de base obsoleta + `journal_version` |

## Qué NO es evidencia en ArqUX

Declarado explícitamente para que el auditor no infiera de más:

- **El brain no es evidencia**: `brain.cortex` es estado mutable de trabajo (focus, lecciones, sesiones). La evidencia vive en timelogs y el PULSE append-only.
- **Los BLPs no son evidencia**: son planes. La evidencia de su ejecución está en el PULSE y los artifacts.
- **Screenshots y logs de terminal no son evidencia**: lo es el evento `AUD`/`DEC`/`ERR` persistido en `.cortex`.
- **El bundle sin sello ni firma es exportación, no prueba**: adquiere valor probatorio al verificarse contra los timelogs y el sello.
- **Marcas `private` no salen en el bundle por defecto**: la evidencia exportable es, por diseño, un subconjunto de la evidencia interna.

## Madurez declarada

| Pieza | Estado 1.0.0 |
|---|---|
| Timelog con timestamps y revisiones | Implementado |
| Sello SHA-256 verificable | Implementado |
| Export de bundle con gate de privacidad | Implementado (REQ-11) |
| Firma Ed25519 sign/verify | Implementado (REQ-12) |
| Journal con optimistic locking | Implementado (REQ-13) |
| HMAC-SHA256 en autenticación de identidad de agente | Implementado (`security.py` — firma de mensajes agente↔workspace) |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="./docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
