---
doc_type: guide
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
<p align="center"><sub>Guía · Informativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Desplegar ArqUX en tu entorno

Guía de despliegue y operación para la versión **1.0.0**. Sustituye a `PILOT_MODE.md` (retirado — describía la línea 0.4.x). Todo valor declarado aquí se verificó contra `pyproject.toml`, el código fuente y mediciones reales.

## Elige tu modo de despliegue

| Modo | Qué es | Cuándo elegirlo |
|---|---|---|
| **Standalone local** | CLI `arqux` sobre un repo; gobierno en `.arqux/` | Un humano (o script) opera el gobierno directamente |
| **Servidor MCP** | `arqux serve` expone 115 handlers por stdio | Un agente (Claude, Cursor, opencode) necesita handlers gobernados |
| **Multi-harness compartido** | MCP + `sync-harnesses` proyecta `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`; journal compartido por el equipo | Varios agentes/personas trabajan sobre el mismo workspace |

Los modos se acumulan: un equipo típico despliega standalone + MCP + proyección de harnesses.

## Prerequisitos y extras

Prerequisitos comunes (los tres modos):

- Python ≥ 3.11
- `pip install arqux` — instala la línea publicada en PyPI (a fecha de esta guía, **0.9.0**; la 1.0.0 de este repo aún no está en PyPI). Para desplegar 1.0.0 hoy: `pip install -e .` desde el repo.

Dependencias de runtime (declaradas en `pyproject.toml`):

- `mcp>=1.0.0,<2` — servidor MCP (pin deliberado: `server.py` usa la API lowlevel)
- `codec-cortex>=1.0,<1.1` — codec CORTEX/HCORTEX (línea 1.0.x, pin de frontera)
- `jsonschema>=4.20`, `click>=8.1.0`, `rich>=13.0.0`

Extras opcionales:

- `pip install "arqux[crypto]"` — `cryptography>=41` solo para la API legacy `arqux.security`. `arqux policy sign/verify` usa Ed25519 en Python puro y **no** lo necesita.
- `pip install "arqux[voice]"` — pipeline de voz local (faster-whisper + Piper/Kokoro + Silero VAD). No requerido para gobierno.
- `pip install "arqux[dev]"` — toolchain de desarrollo (pytest, ruff, mypy, pre-commit).

## Despliegue por modo

### 1. Standalone local

```bash
pip install -e .            # o pip install arqux para la línea PyPI
cd mi-repo
arqux init                  # crea .arqux/ + AGENTS.md — ~0.2s
```

`.arqux/` es el único estado del producto: brain, blueprints, journal, identidades, políticas. Borrar `.arqux/` = desinstalar el gobierno (los archivos de proyecto quedan intactos).

### 2. Servidor MCP para agentes

```bash
arqux serve                 # stdio, un workspace por proceso
```

Registra el servidor en el cliente MCP (mismo patrón en todos):

```json
{"mcpServers": {"arqux": {"command": "arqux", "args": ["serve"], "cwd": "/ruta/al/workspace"}}}
```

Un `tools/list` debe devolver los 115 handlers. Si el agente se identifica, exporta `ARQUX_AGENT_ID` (ver tabla env) antes de lanzar el cliente.

### 3. Multi-harness compartido

```bash
arqux sync-harnesses        # genera AGENTS.md, CLAUDE.md, GEMINI.md, .opencode/instructions.md
arqux drift-check           # verifica que las proyecciones no se editaron a mano
arqux pull-policy           # trae el journal del equipo
arqux push-delta            # publica tus deltas
```

Detalles del ritual en [Sincronizar equipo](sincronizar-equipo.md) y [Proyectar el gobierno](proyectar-agentes.md).

## Variables de entorno

Vars de despliegue relevantes (grep-verificado contra `src/arqux/`) — la lista exhaustiva está en [Configuración](../referencia/configuracion.md):

| Variable | Para qué | Default |
|---|---|---|
| `ARQUX_DIR` | Raíz del estado gobernado | `.arqux/` en el cwd |
| `ARQUX_AGENT_ID` | Identidad del agente que llama | anónimo (warning al init) |
| `ARQUX_AGENT_ROLE` | Rol: `GOVERNOR` / `EXECUTOR` / `AUDITOR` | `EXECUTOR` |
| `ARQUX_AGENT_SECRET` | Secreto HMAC para handlers firmados | vacío (firmado deshabilitado) |
| `ARQUX_AGENT_SIGNATURE`, `ARQUX_AGENT_TIMESTAMP` | Firma+ts de la llamada (handlers HMAC) | — |
| `ARQUX_EXECUTION_KEY` | Clave de elevación de ejecución | — |
| `ARQUX_STRICT_ROLES` | Deniega roles no declarados | off |
| `ARQUX_STRICT_SECURITY` | Hardening de la superficie de seguridad | off |
| `ARQUX_STRICT_EXECUTION` | Ejecución estricta de blueprints | off |
| `ARQUX_ALLOW_IMPLICIT_EXECUTION` | Permite ejecutor implícito por contexto | off |
| `ARQUX_COMMS_EGRESS` | Salida del bridge de comms | off |
| `ARQUX_COMMS_ALLOWLIST` | Lista blanca de destinos comms | — |
| `ARQUX_COMMS_TELEGRAM_TOKEN` | Token del bot Telegram (bridge) | — |

Detalle por escenario en [Configuración](../referencia/configuracion.md).

## Journal compartido (topología honesta)

El journal (`journal.cortex`) es la evidencia append-only del workspace. No hay servidor propio: el transporte es **archivo** — el equipo lo comparte por el medio que ya use (repo git, mount compartido, artefacto CI).

- `arqux push-delta` empaqueta tus deltas; `arqux pull-policy` aplica los del equipo.
- Conflicto de versiones concurrentes → `ERR_CONFLICT_VERSION`; resolución documentada en [Sincronizar equipo](sincronizar-equipo.md).
- El journal es verificable offline — la cadena se audita sin servidor ArqUX.

## Hardening

Checklist mínimo de producción:

- [ ] `.arqux/keys/` (si existe material de firma): `chmod 700`, claves `chmod 600`
- [ ] `ARQUX_AGENT_SECRET` en gestor de secretos — **nunca** en el repo ni en `AGENTS.md`
- [ ] `.gitignore`: `.arqux/keys/`, `*.secret`, venvs; el resto de `.arqux/` **sí** se versiona (es la evidencia)
- [ ] `ARQUX_STRICT_ROLES=1` y `ARQUX_STRICT_SECURITY=1` en entornos multiagente
- [ ] Backup del journal: es archivo plano — incluir `.arqux/journal.cortex` en el backup del repo
- [ ] Pin de dependencias en producción (`codec-cortex>=1.0,<1.1` ya viene acotado)

## Rendimiento medido

Medido en esta máquina de desarrollo (Linux, Python 3.11, CPU modesta — tratar como rango, no contrato):

| Operación | Medición |
|---|---|
| `arqux --version` | ~0.16 s |
| `arqux wake` | ~0.2 s (serializa+renderiza brain) |
| `arqux init` | <1 s |
| Suite completa `pytest` | 2920 tests, ~1–2 min según máquina |

El producto es I/O sobre archivos `.cortex` planos: el coste dominante es parsear el brain, que crece con su tamaño — `cortex.gc` y el compactado periódico lo mantienen acotado.

## Checklist de go-live

- [ ] `arqux doctor` verde en el workspace
- [ ] `tools/list` devuelve 115 handlers desde el cliente MCP
- [ ] `ARQUX_AGENT_ID`/role exportados por agente
- [ ] `sync-harnesses` ejecutado + `drift-check` en verde
- [ ] Journal incluido en backup; claves fuera del repo
- [ ] `pytest tests/e2e/test_docs_contract.py` verde (docs honestas)

## Ver también

- [Arrancar un agente](arranque-agente.md) — el ritual `arqux wake` por rol
- [Auditar el trabajo](auditar-trabajo.md) — revisión de lo desplegado
- [ARCHITECTURE.md](../../../ARCHITECTURE.md) — internals del producto

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
