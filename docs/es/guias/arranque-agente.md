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

# Arrancar un agente con contexto gobernado

`arqux wake --identity <rol>` entrega al agente su contexto en una llamada: **quién es, qué proyectos existen, en qué estado está el trabajo, qué reglas aplican y qué tarea tiene en curso**. Es el sustituto gobernado del system prompt inflado.

Medidas reales en este workspace: **183 ms**, **2 875 bytes** (~800 tokens — bajo el presupuesto <1500 declarado en REQ-08), salida `cortex:1.0`.

```bash
arqux wake --identity executor --path /ruta/al/workspace
```

## Qué devuelve — salida real anotada

```cortex
$0
$0:format{cortex:1.0, encoding:UTF-8}
ARQX:arqx_contract{...} DOM:dom_contract{...} IDN:idn_contract{...} ...

$19: ARQUX METADATA
ARQX:artifact{level:0, name:"wake-executor", usage:"state", kind:"projection"}

$1: WAKE
IDN:wake{identity:"executor", kind:"generic",
         workspace:"/home/vatrox/workspace", project:"none", cycle:"none"}

$2: REGISTRY
DOM:arqux{name:"ARQUX", status:"current", updated:"2026-11-15T22:05:56Z",
          last_event:"blueprint.complete"}
DOM:codec_cortex{name:"CODEC-CORTEX", status:"current", ...}
...                                       ← proyectos del workspace, con último evento

$3: STATE
WRK:current{name:"workspace", project:"Proyecto_X", scope:"CYCLE-01",
            agent:"Alfred", phase:"consolidation", current:"GRADIENT-12 aplicado",
            state:"iter4_done", task:"VAMOS loop iter-4: ...", pendiente:"..."}

$4: RULES

$5: TASK
TSK:none{task_id:"none", note:"no in-progress task"}
```

| Sección | Contenido | Para qué sirve al agente |
|---|---|---|
| `$0` + contratos | Glosario local autocontenido | El archivo se parsea solo, sin contexto externo |
| `$1 WAKE` | Identidad, kind, workspace, project, cycle | "Quién soy y dónde estoy" |
| `$2 REGISTRY` | `DOM:` por proyecto: estado, ciclo, último evento | El mapa del workspace sin explorar |
| `$3 STATE` | `WRK:current`: foco, fase, tarea, pendientes | "Qué estaba pasando" — continuidad real |
| `$4 RULES` | Reglas de política aplicables | "Qué no puedo hacer" |
| `$5 TASK` | Tarea en curso o `TSK:none` | "Qué hago ahora" |

> Ejemplo capturado con el workspace real; en un workspace mínimo verás menos `DOM:` — la estructura es la misma.

## Roles e identidades válidas

`--identity` acepta cualquier identidad registrada en `.arqux/identities/*.cortex`. En este workspace: `alfred`, `auditor`, `executor`, `governor`, `heimdall`, `jarvis`, `seshat`.

Un rol inexistente produce error + la lista de válidos (exit 1):

```bash
$ arqux wake --identity fulano --path /workspace
unknown identity 'fulano'. Valid contracts: alfred, auditor, executor, governor, heimdall, jarvis, seshat
```

## Integración en el bootstrap del agente

Tres puntos concretos donde `wake` reemplaza contexto escrito a mano:

**1. Antes del primer turno (hook de sesión del harness).**

```bash
# en tu wrapper/entrypoint del agente
WAKE=$(arqux wake --identity executor --path "$WORKSPACE")
# → inyecta $WAKE como primer mensaje de contexto del LLM
```

El agente arranca sabiendo el estado real del workspace — no lo que el system prompt de hace una semana decía.

**2. En AGENTS.md como instrucción de arranque.**

```markdown
## Arranque
Antes de actuar: ejecuta `arqux wake --identity executor --path <workspace>`
y trata su salida como tu estado actual.
```

Funciona en cualquier harness que lea AGENTS.md (ver [proyección multi-harness](proyectar-agentes.md)) — el agente se auto-boostrapea.

**3. Refresh periódico en sesiones largas.**

Después de un hito (cierre de tarea, cambio de ciclo), re-ejecuta `wake` — el REGISTRY y STATE reflejan el nuevo punto. 183 ms hace que refrescar sea barato.

## Notas honestas

- **`kind:"generic"`**: el payload describe identidad+registro+estado; no incluye el contrato conductual completo de la identidad (ese vive en `.arqux/identities/<id>.cortex`).
- **Diagnóstico conocido:** si dos proyectos del workspace comparten nombre, sus `DOM:` colisionan y el codec reporta `I006_DUPLICATE_IDEA_ADDRESS` al validar — verificado en este workspace. La salida sigue siendo legible; la deduplicación de nombres es trabajo pendiente del generador.
- La salida cambia con el estado: `WRK:current` y `TSK:` reflejan lo que hay *ahora*, no una plantilla fija.

## Cheatsheet

| Quiero | Comando |
|---|---|
| Contexto de arranque para un agente | `arqux wake --identity <rol> --path <ws>` |
| Ver roles válidos | `ls .arqux/identities/` (o provocar el error — te los lista) |
| Refrescar estado mid-session | re-ejecutar `wake` (183 ms) |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
