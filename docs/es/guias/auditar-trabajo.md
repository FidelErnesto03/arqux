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

# Auditar el trabajo de un agente

Ritual de revisión para quien firma el trabajo ajeno: **review → integridad → actores → decisión**. ~10 minutos la primera vez; ~2 minutos cuando es rutina.

```text
1. arqux review --cycle CYCLE-NN    → qué se hizo, con métricas
2. arqux cortex-verify <archivo>    → integridad no fue alterada
3. arqux call evidence.list         → quién hizo qué, cuándo
4. Decides: aprobar o escalar       → con datos, no con fe
```

## Paso 1 — Leer el review del ciclo

```bash
$ arqux review --cycle CYCLE-16
# Cycle Review — CYCLE-16

| Field | Value |
|---|---|
| Status | active |
| Seal | `none` |
| Entries | 2 |
| Tasks | 0 |

## Evidence (HCORTEX — round-trippable)
## §19: ARQUX METADATA
## §1: CYCLE
...
```

Qué mirar en la salida:

| Campo | Dónde | Sospechoso si |
|---|---|---|
| `Status` | cabecera | `closed` sin seal, o ciclo "terminado" que sigue `active` |
| `Seal` | cabecera | `none` en un ciclo que debería estar cerrado y sellado |
| `Entries`/`Tasks` | cabecera | 0 entradas en un ciclo que reporta trabajo hecho |
| Secciones `§` | cuerpo HCORTEX | secciones de evidencia vacías o ausentes |

El cuerpo HCORTEX es round-trippable: es el estado del ciclo compilado a formato legible — `loss_count == 0` significa que nada se perdió al recompilar (REQ-09).

## Paso 2 — Verificar integridad

```bash
$ arqux cortex-verify .arqux/brain.cortex
OK: .arqux/brain.cortex integrity verified
```

- Exit `0` = integridad verificada; exit `1` = alteración o cabecera ausente.
- Los archivos `.cortex` escritos con cadena de integridad llevan `# $INTEGRITY: sha256:<hash>` en la primera línea — el verify rehashea el contenido y compara.

**Demostración real de la protección** (archivo con `$INTEGRITY`, un byte alterado):

```bash
$ arqux cortex-verify /tmp/integrity-tampered.cortex
FAIL: integrity violation in /tmp/integrity-tampered.cortex:
expected=496280aa97…, actual=2a90e64f6a…
# exit code 1
```

> **Detalle honesto:** `verify` comprueba la cabecera `$INTEGRITY` cuando existe — un archivo sin ella pasa sin comparación. La capa fuerte de un ciclo es su **seal**.

### El seal del ciclo (capa fuerte)

Al cerrar un ciclo (`cycle.close`), ArqUX escribe `seal.cortex`: un SHA-256 por cada artefacto `.cortex` del ciclo más un hash raíz sobre el conjunto, anclado en el MANIFEST (`seal_sha256`). `cortex-verify` sobre `seal.cortex` **recomputa cada hash** y reporta `ERR_HASH_MISMATCH` ante cualquier deriva (REQ-03).

> seal = **integridad** ("el contenido no cambió"), firma Ed25519 = **no-repudio** ("quién lo produjo"). Para verificación de firma de bundles: [guía de evidencia y cumplimiento](evidencia-y-cumplimiento.md).

## Paso 3 — Rastrear actores

```bash
$ arqux call evidence.list cycle=CYCLE-16
OUT-WORK events=SES021-E0001,SES022-E0001,...,SES022-E0099
total=105 returned=100 offset=0 next_offset=100 storage=brain.pulse
```

- `evidence.list` filtra por `task_id`, `cycle`, `since` (paginado `limit`/`offset`).
- Cada evento lleva su sesión en el ID (`SES022-E0093` → sesión 22, evento 93): **quién y cuándo** sin excavar logs.
- `evidence.read event_id=SES022-E0093` da el detalle del evento.
- Los eventos de auditoría firman como `OUT-AUDIT` — si el ejecutor reporta "verificado" pero la evidencia no trae el audit independiente, no está auditado.

## Checklist de aprobación

- [ ] `review` muestra los ACs del ciclo/BLP marcados y la evidencia enlazada
- [ ] `Seal` presente si el ciclo está cerrado (o entiendes por qué `none`)
- [ ] `cortex-verify` OK en los artefactos clave; seal OK si existe
- [ ] `evidence.list` muestra eventos coherentes con lo reportado (mismas tareas, actores esperados)
- [ ] Sin `drift` pendiente (`arqux drift-check` si usas proyecciones)

## Señales que exigen escalación

- `Seal` ausente en ciclo cerrado, o `seal_sha256` del MANIFEST que no coincide
- `ERR_HASH_MISMATCH` / `integrity violation` en cualquier artefacto — **no aprobar nada**
- Eventos de evidencia que no corresponden a las tareas reclamadas
- ACs "verificados" sin `OUT-AUDIT` asociado
- `Status` del ciclo inconsistente con el reporte verbal del ejecutor

Escalar = abrir issue + pedir al gobernador una verificación `OUT-AUDIT` formal. La evidencia firmada existe precisamente para que esta conversación sea corta.

## El ritual cronometrado (ejemplo real)

| Minuto | Acción |
|---|---|
| 0–2 | `review --cycle` — panorama y secciones de evidencia |
| 2–4 | `cortex-verify` en artefactos clave / seal |
| 4–7 | `evidence.list` — actores y cadena de eventos |
| 7–10 | checklist + decisión |

En rutina (~2 min): los tres comandos + vistazo al checklist. La primera vez cuesta más porque estás calibrando qué es normal — es tiempo bien gastado.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
