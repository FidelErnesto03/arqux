<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="./docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<!-- /DOC-BRAND -->

<div align="center">

# ⬡ ArqUX

**Infraestructura de gobernanza por debajo de tu stack de agentes.**

[![Version](https://img.shields.io/badge/version-1.0.0-167A55?style=flat-square&labelColor=050807)](https://pypi.org/project/arqux/)
[![Status](https://img.shields.io/badge/status-stable-2EC98D?style=flat-square&labelColor=050807)](https://pypi.org/project/arqux/)
[![License](https://img.shields.io/badge/license-Apache--2.0-2EC98D?style=flat-square\&labelColor=050807)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-8FE3C0?style=flat-square&labelColor=050807)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-governance%20layer-167A55?style=flat-square&labelColor=050807)](https://github.com/FidelErnesto03/arqux)
[![Getting Started](https://img.shields.io/badge/Getting%20Started-guide-2EC98D?style=flat-square&labelColor=050807)](docs/en/tutorial/inicio-rapido.md)
[![Handlers](https://img.shields.io/badge/MCP%20Handlers-116-purple)](https://github.com/FidelErnesto03/arqux)
[![Agents](https://img.shields.io/badge/agents-7-red)](https://github.com/FidelErnesto03/arqux)
[![Coverage](https://img.shields.io/badge/coverage-71%25-orange)](https://github.com/FidelErnesto03/arqux)
[![CORTEX](https://img.shields.io/badge/CORTEX-persistent%20memory-2EC98D?style=flat-square&labelColor=050807)](https://github.com/FidelErnesto03/codec-cortex)

**Audit. Replay. Query.**

</div>

---

## El problema en tres líneas

Los agentes olvidan, improvisan, y nadie puede probar qué sabían cuando actuaron.
La memoria agéntica actual es estadística: recall probabilístico, sin integridad, sin rastro.
ArqUX lo resuelve en la capa de almacenamiento — no en el prompt.

## Qué es y qué no es

| ArqUX **es** | ArqUX **no es** |
|---|---|
| Gobernanza por debajo de tu stack de agentes | Una plataforma más — es la capa que hace gobernable la tuya |
| Un formato de memoria determinista, certificado byte-exact en 5 runtimes | Un caché de prompts ni una colección de system prompts |
| Un journal encadenado por hash con orden total de escritura | Un reemplazo del modelo — el modelo razona, ArqUX gobierna |
| Contratos de identidad con axiomas, límites y evidencia firmada | Un personality pack ni una skin de interfaz |

## Quick start

```bash
pip install arqux
mkdir mi-workspace && cd mi-workspace
arqux init     # crea .arqux/ + AGENTS.md
arqux serve    # expone la gobernanza por MCP (stdio)
```

```text
OUT-MIN workspace=./.arqux governor=anonymous workspace.init ok
```

Verificado en máquina limpia: `pip install arqux` publica hoy la línea 0.9.x en PyPI — este repositorio ya corre 1.0.x.

Tu agente entra leyendo el contrato de gobernanza — no adivinando:

```bash
opencode --instructions "$(cat AGENTS.md)"
```

## Qué hace la 1.0

| Capacidad | Hecho verificable |
|---|---|
| Gobernanza por MCP | 115 handlers: sesión, ciclo, blueprint, evidencia, identidad, timelog |
| Contratos de identidad | 7 identidades con axiomas y límites explícitos; `arqux wake --identity` entrega estado y reglas en <1500 tokens (REQ-08) |
| Memoria CORTEX | Formato canónico certificado byte-exact en 5 runtimes |
| Integridad sellada | `seal.cortex` con SHA-256 por artefacto; `arqux cortex-verify` detecta tampering (REQ-03) |
| Multi-harness | `sync-harnesses` proyecta a `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.opencode/`; `drift-check` detecta ediciones manuales (REQ-07) |
| Evidencia exportable | `evidence export` empaqueta spans en `bundle.cortex`; `policy sign/verify` firma Ed25519 pura (REQ-11, REQ-12) |
| Journal autoritativo | `push-delta`/`pull-policy` con orden determinista y `ERR_CONFLICT_VERSION` ante conflicto (REQ-13) |
| Calidad medida | 2920 tests en la suite |

## Agentes soportados

- **Nivel 1 — archivos (universal):** cualquier agente que sepa leer `AGENTS.md` y escribir `.cortex`.
- **Nivel 2 — MCP (completo):** cualquier cliente del Model Context Protocol.

Codex, OpenCode, Gemini CLI, z.ai, Qwen, Devin: no comparten runtime ni modelo — comparten `.arqux/`.

## Documentación

| Si vienes a… | Empieza por |
|---|---|
| Evaluar el producto | [`docs/es/README.md`](docs/es/README.md) — índice canónico en español |
| Aprender haciendo | [`docs/en/tutorial/inicio-rapido.md`](docs/en/tutorial/inicio-rapido.md) |
| Consultar CLI, errores, configuración, formatos | [`docs/es/referencia/`](docs/es/referencia/) |
| Leer la especificación CORTEX (ES, corpus de origen) | [`docs/es/especificacion/`](docs/es/especificacion/) |
| Auditar evidencia y cumplimiento | [`EVIDENCE.md`](EVIDENCE.md) · [`docs/es/guias/evidencia-y-cumplimiento.md`](docs/es/guias/evidencia-y-cumplimiento.md) |
| Ver la superficie MCP completa | [`HANDLERS.md`](HANDLERS.md) |
| Entender la arquitectura y los porqués | [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/es/explicacion/`](docs/es/explicacion/) |

## Seguridad · Contribuir · Licencia

- Reporte de vulnerabilidades: [`SECURITY.md`](SECURITY.md)
- Cómo contribuir: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Licencia **Apache-2.0**: [`LICENSE`](LICENSE)

---

<div align="center">

**⬡ ArqUX** — Audit. Replay. Query.

```text
El archivo es el protocolo.
La Q es el journal.
Tus datos quedan en tu terreno.
```

</div>

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · <a href="./docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
