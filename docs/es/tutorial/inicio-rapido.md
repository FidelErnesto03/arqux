---
doc_type: tutorial
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
<p align="center"><sub>Tutorial · Informativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Inicio rápido — tu primer workspace gobernado en ~10 minutos

Construirás un workspace ArqUX desde cero: instalarás el paquete, inicializarás la gobernanza, registrarás un proyecto con su primer ciclo y blueprint, y conectarás un agente real por MCP. Al final, el agente responde preguntas que solo puede saber leyendo el brain del proyecto.

## Lo que necesitas

- Python 3.10+ y ~10 minutos.
- Un cliente MCP (Claude Desktop en el ejemplo; cualquier cliente stdio sirve).
- Linux o macOS — los comandos se verificaron en Linux (arqux 0.9.0 desde PyPI; este repo ya corre 1.0.x).

## Paso 1 — Instala ArqUX

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install arqux
```

Verás:

```text
Successfully installed arqux-0.9.0
```

## Paso 2 — Inicializa el workspace

```bash
mkdir mi-workspace && cd mi-workspace
arqux init
```

Verás:

```text
OUT-MIN workspace=./.arqux governor=anonymous workspace.init ok
```

Acabas de crear dos cosas: `AGENTS.md` en la raíz — el contrato de gobernanza que todo agente lee primero — y `.arqux/` con `meta-brain.cortex` (memoria del workspace), `projects.cortex` (registro), `identities/` (7 contratos de rol) y `skills/`. Sin servidor, sin API key: un directorio.

> Opcional: `export ARQUX_AGENT_ID=alfred` fija la identidad del operador (`governor=Alfred` en la salida). La identidad del *agente* la define su lectura de `AGENTS.md`, no esta variable.

## Paso 3 — Registra un proyecto

```bash
mkdir mi-proyecto && cd mi-proyecto
arqux project init name=mi-proyecto
```

El comando imprime las instrucciones de seeding del brain y termina creando `.arqux/brain.cortex` — la memoria gobernada del proyecto.

## Paso 4 — Crea el primer ciclo y su manifiesto

```bash
arqux cycle create name=CICLO-01
```

Verás:

```text
OUT-WORK cycle_id=CYCLE-01 status=draft ... cycle.create ok id=CYCLE-01 status=draft
```

El ciclo nace en `draft`: el manifiesto plantilla exige contenido real antes de alojar blueprints. Rellénalo con una llamada:

```bash
arqux call cycle.synthesize cycle_id=CYCLE-01 content='$1:{Proposito: validar el flujo gobernado de punta a punta.} $2:{Dentro: primer ciclo y blueprint de prueba. Fuera: trabajo real.} $3:{Objetivo: un blueprint creado bajo gobierno.} $4:{Regla: escrituras solo via handlers.} $5:{Puntos de control: crear ciclo, crear blueprint. Fechas: hoy.} $6:{Indice de blueprints del ciclo.} $7:{Estado: prueba. Metricas: blueprints creados.} $8:{Regla: mutaciones solo por handlers. Regla: cierre con evidencia.} $9:{Calidad: salidas reales verificadas.}'
```

Verás:

```text
OUT-WORK cycle_id=CYCLE-01 sections_written=1,2,3,4,5,6,7,8,9 cycle.synthesize ok
```

## Paso 5 — Crea el primer blueprint

```bash
arqux call blueprint.create obj="Primer blueprint de prueba"
```

Verás:

```text
OUT-WORK blueprint_id=BLP-001 cycle=CYCLE-01 status=draft markers=BLP:TITLE,BLP:1,...,BLP:18 blueprint.create ok
```

El blueprint es un documento de decisión de 18 secciones en `.arqux/cycles/CYCLE-01/blueprints/BLP-001.md` — existe antes de ejecutarse nada. Esa es la idea central: la arquitectura se piensa antes de mutarse.

## Paso 6 — Conecta un agente por MCP

`arqux serve` expone los 115 handlers de gobernanza por stdio. Añade el servidor a tu cliente:

**Claude Desktop** — `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/` · Linux: `~/.config/Claude/`)

```json
{
  "mcpServers": {
    "arqux": {
      "command": "arqux",
      "args": ["serve"]
    }
  }
}
```

**Cualquier cliente stdio** — equivale a lanzar:

```bash
cd mi-workspace && arqux serve
```

El servidor resuelve `.arqux/` subiendo directorios desde su directorio de trabajo — lánzalo con el workspace como cwd.

## Paso 7 — Verificación gobernada

Reinicia el cliente y pregúntale al agente algo que **solo puede saber por el brain**:

> ¿Qué proyecto hay en este workspace, qué ciclo está abierto y qué blueprint existe?

El agente consulta los handlers (`project.status`, `cycle.current`, `blueprint.list`) y responde: proyecto `mi-proyecto`, ciclo `CYCLE-01`, blueprint `BLP-001` en draft. Esa respuesta es la prueba: contexto real, no adivinanza.

## Funcionó si…

- [ ] `arqux init` creó `AGENTS.md` y `.arqux/` (exit 0)
- [ ] `arqux project init` creó `.arqux/brain.cortex` en el proyecto
- [ ] `cycle.synthesize` devolvió `sections_written=1..9`
- [ ] `blueprint.create` devolvió `blueprint_id=BLP-001`
- [ ] El cliente MCP lista los tools de `arqux` y el agente responde con datos del brain

## Qué acabas de aprender

- La gobernanza es un directorio: `AGENTS.md` + `.arqux/`, sin servidor ni SDK.
- El trabajo se piensa antes de ejecutarse: ciclo → manifiesto → blueprint.
- El agente no adivina: lee el contrato y consulta handlers MCP.

## A dónde ir ahora

| Si eres… | Sigue con |
|---|---|
| Referencia exacta de comandos | [`../referencia/cli.md`](../referencia/cli.md) |
| Contrato de errores | [`../referencia/errores.md`](../referencia/errores.md) |
| Configuración (env vars, rutas, permisos) | [`../referencia/configuracion.md`](../referencia/configuracion.md) |
| Especificación del formato CORTEX | [`../especificacion/`](../especificacion/) |
| Arquitectura y decisiones | [`ARCHITECTURE.md`](../../../ARCHITECTURE.md) · [`../explicacion/`](../explicacion/) |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
