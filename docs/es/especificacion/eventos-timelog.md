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

# Ciclo de vida de los eventos — timelog `$5 EVENTS`

**Estado:** canon vigente (modelo destino) + referencia histórica T1
(ALFRED · CYCLE-16 · 2026-11-15).
**Carpeta:** `docs/es/especificacion/` — este documento responde *"¿dónde viven y
cómo circulan los eventos?"*.

---

## 1. Ciclo de vida de los eventos — timelog `$5 EVENTS` (modelo destino)

**Principio:** un evento (`AUD`/`DEC`/`ERR`) pertenece a la sesión que lo
produjo. El brain es memoria *inter*-sesión; el timelog es memoria
*intra*-sesión. Bajo este canon, la sección `PULSE` desaparece del brain
y cada timelog gana una sección más:

```
$0  glosario timelog (+ declaración AUD/DEC/ERR)
$1  IDENTITY    TLG:identity{project, ses, opened, version, revision}
$2  ACTIVITIES  ACT:*{start, end, state, ...}        (intervalos — hoy)
$3  RECEIPTS    RCV:*                                (proyección externa)
$4  PROJECTIONS PRJ:*                                (marcas por proveedor — hoy)
$5  EVENTS      AUD:SES021-E0042{kind, event, ...}   (eventos — NUEVO;
                en disco se almacena underscore E_NNNN — separador del codec)
```

### 1.1 Emisión

- Todo handler que llama `record_pulse()`/`evidence.record` emite el
  `AUD`/`DEC`/`ERR`/`LOOP` a `$5 EVENTS` del timelog de la sesión activa.
  La mayoría de los emisores **no pasa `ses_ref` explícito**: desde
  CYCLE-16 `record_pulse` lo auto-resuelve desde el execution/sesión
  ambiental (`_resolve_ses_ref` — `authoritative_execution_key()` +
  `current_session_ref()`); solo cae al PULSE legado del brain cuando no
  hay sesión ligada.
- **Concurrencia gratis:** cada agente/sesión escribe su propio archivo
  con su propio lock — la vía de escritura más caliente del sistema deja
  de competir por el lock del brain.
- **IDs con namespace:** `SESNNN-EXXXX` — secuencia por sesión, sin
  escaneo global del brain para incrementar. `E-XXXX` queda como compat
  cuando no hay `ses_ref` resoluble.
- **Sigilos admitidos en `$5 EVENTS`:** `AUD`, `DEC`, `ERR`, `LOOP`
  (`timelog_store.EVENT_SIGILS`; `loops.log_event` enruta su trail por
  `append_event` — nunca append crudo fuera de `$5`).

### 1.2 Durabilidad y consulta

- **Append-only, nunca podado.** La evidencia se vuelve verdaderamente
  durable: hoy T1 la recorta silenciosamente (`evidence.list` sobre
  eventos viejos ya devuelve vacío — la "durabilidad" era ficción).
- **Lectura por sesión** = leer su timelog (sesión activa, dashboard,
  forense). **Lectura cross-sesión** (`evidence.list`, aprendizaje) =
  escanear timelogs — enumerables por nombre/fecha, cacheable por
  `revision`.
- **Handoffs:** el evento se anota en el timelog del *emisor*; la cola
  de pendientes vive como `HND:<to>` en brain `$7` (cerebro-canon.md §3).

### 1.3 Efectos sobre el brain

- `PULSE` deja de existir como sección — el brain queda en **11
  secciones** (`$0`–`$10`) y pierde ~50% de sus entradas (276 de ~560).
- `WRK:current` (`$7`) sigue siendo la respuesta a "dónde quedé"; los
  eventos del *cómo* viven en la sesión.
- T1/T2/T3 **quedan retirados**: ya no hay nada que podar en el brain.
  `LNG:pulse_sweep` y `session.pulse.gc` se deprecan con la migración.

### 1.4 Legado — migrado en G-8

Los `AUD` históricos del brain (**276** en `$7`, verificado por
conteo directo — audits previos citaban 285 erróneamente) se
archivaron a `.arqux/archive/hygiene-2026-11-15/pulse-legacy.cortex`.
Alternativa canónica (migración al timelog de su `ses_ref`) quedó
descartada en la operación — el archive preserva la evidencia sin
reescritura forense. La lectura `PULSE` en brains antiguos queda como
compat-legacy, igual que `$0.1`/`$15`/`$19` para metadata
(`formato.md`).

**Advertencia cerrada (CYCLE-16)**: `pulse.py` ya enruta `AUD` al
timelog `$5 EVENTS` cuando hay `ses_ref`, y al fallback PULSE *por
título* cuando no — nunca a `$7` posicional (que bajo el nuevo layout
es `ACTIVE_CONTEXT`).

### 1.5 Mecanismo T1 — RETIRADO (CYCLE-16)

T1 quedó **retirado del write-path**: el auto-sweep ya no se dispara en
cada `record_pulse`. Los eventos del timelog `$5 EVENTS` son append-only
y **nunca se podan** (`_prune_timelog_events` = no-op deliberado). Los
handlers `sweep`/`compact` explícitos sobreviven solo como mantenimiento
best-effort del PULSE legado del brain (residuo pre-migración), y
`LNG:pulse_sweep` sigue siendo la lección-censo que emiten. La señal
`pulse density` de doctor reporta densidad informativa, sin poda
automática.

---

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
