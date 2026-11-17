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
<p align="center"><sub>Canon · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Canon — `timelog/SESNNN_*.cortex` (sesión / episódico)

**Estado:** canon vigente (ALFRED · CYCLE-16 · 2026-11-15, auditado
por Heimdall).
**Alcance:** `<project>/.arqux/timelog/` — un artefacto por sesión.

---

## 1. Qué es

El **artefacto intra-sesión**: escribe por defecto, nunca resume
(AXM-2). Memoria episódica append-only de la sesión — la fuente de
la que el motor de aprendizaje produce lecciones.

| Propiedad | Valor |
|---|---|
| Ubicación | `<project>/.arqux/timelog/` — proyecto únicamente |
| Nombrado | `SESNNN_YYYYMMDD_HHMMSS.cortex` — **sin marca de agente** (21 archivos actuales) |
| Writer | `session.context.set`/`close`, `cortex.checkpoint` vía `observe()` — **no existe `session.open`** |
| Operación | locks transitorios `*.lock` durante escritura (limpiados al finalizar) |

## 2. Layout real (verificado en corpus)

```
$0: <título>            comentario título (corpus pre-1.0: sin
                        $0:format — el serializer vigente
                        timelog_store.py:54-79 SÍ emite dialecto
                        completo + 5 contratos en la próxima
                        reescritura)
$1: IDENTITY            TLG:identity{project, ses, opened,
                        version, revision}
$2: ACTIVITIES          ACT:*{start, end, state, revision,
                        last_activity?} — append-only
$3: RECEIPTS            RCV:* — hoy vacío en el corpus
$4: PROJECTIONS         PRJ:* — hoy vacío en el corpus
```

Notas reales:

- **`$4` ausente en 7 archivos** (SES002–012): el split sigue la
  fecha de re-serialización vs soporte PRJ (T-038, 2026-10-22) —
  no una migración única.
- **`$5 EVENTS` = modelo-destino** (eventos-timelog.md): hoy los eventos
  AUD van al brain `$7` posicional (= `ACTIVE_CONTEXT` post-GRADIENT —
  colisión activa); la reclasificación AUD→timelog es deuda G-3b.
- **`last_activity` vive en `$2`** en las `ACT:*` de los archivos
  re-serializados (heartbeat del servidor, `timelog_store.py:175`),
  nunca en `TLG:identity`.
- El serializer vigente además inserta `ARQX:artifact{level:"0",
  name:"timelog"}` en `$1` (timelog_store.py:160) — corpus aún sin él.
- Grafía de eventos: IDs canónicos `E-NNNN` (hyphen) almacenados como
  `E_NNNN` (underscore — hyphen es separador de selector del codec);
  el modelo-destino prescribe `SESNNN-EXXXX` por sesión (G-3b).

## 3. Relación con el brain (la división)

| Timelog (episódico) | Brain (semántico) |
|---|---|
| cada paso, sin evaluar | lo extraído y evaluado |
| `ACT`/`RCV`/`PRJ` | `AUD`/$5, `DEC`, `LNG`… |
| vida = la sesión | vida = el proyecto |
| `timelog.query` por sesión | `cortex.read` por sección |

La sesión muere; el brain hereda solo lo que merece persistir
(`$10` → eventos `$5` → lecciones `$8` → conocimiento `$3`).

## 4. Referencias

- `cerebro-canon.md` §1.2 — por qué el timelog no vive en el brain
- `eventos-timelog.md` — `AUD`/`DEC` del brain → `$5` (modelo-destino)
- `artefactos.md` §2.4 — ficha nivel 0

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
