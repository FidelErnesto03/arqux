<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../../docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="../../../docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<!-- /DOC-BRAND -->

# ⬡ ArqUX

**Governance infrastructure underneath your agent stack.**

[![Version](https://img.shields.io/badge/version-1.0.0-167A55?style=flat-square&labelColor=050807)](https://pypi.org/project/arqux/)
[![Status](https://img.shields.io/badge/status-stable-2EC98D?style=flat-square&labelColor=050807)](https://pypi.org/project/arqux/)
[![License](https://img.shields.io/badge/license-Apache--2.0-2EC98D?style=flat-square\&labelColor=050807)](../../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-8FE3C0?style=flat-square&labelColor=050807)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-governance%20layer-167A55?style=flat-square&labelColor=050807)](https://github.com/FidelErnesto03/arqux)
[![Getting Started](https://img.shields.io/badge/Getting%20Started-guide-2EC98D?style=flat-square&labelColor=050807)](../tutorial/inicio-rapido.md)
[![Handlers](https://img.shields.io/badge/MCP%20Handlers-115-purple)](https://github.com/FidelErnesto03/arqux)
[![Agents](https://img.shields.io/badge/agents-7-red)](https://github.com/FidelErnesto03/arqux)
[![Coverage](https://img.shields.io/badge/coverage-71%25-orange)](https://github.com/FidelErnesto03/arqux)
[![CORTEX](https://img.shields.io/badge/CORTEX-persistent%20memory-2EC98D?style=flat-square&labelColor=050807)](https://github.com/FidelErnesto03/codec-cortex)

**Audit. Replay. Query.**

---

## The problem in three lines

Agents forget, improvise, and nobody can prove what they knew when they acted.
Today's agent memory is statistical: probabilistic recall, no integrity, no trail.
ArqUX solves it at the storage layer — not in the prompt.

## What it is and what it is not

| ArqUX **is** | ArqUX **is not** |
|---|---|
| Governance underneath your agent stack | Another platform — it is the layer that makes yours governable |
| A deterministic memory format, byte-exact certified in 5 runtimes | A prompt cache or a collection of system prompts |
| A hash-chained journal with total write ordering | A model replacement — the model reasons, ArqUX governs |
| Identity contracts with axioms, limits and signed evidence | A personality pack or an interface skin |

## Quick start

```bash
pip install arqux
mkdir my-workspace && cd my-workspace
arqux init     # creates .arqux/ + AGENTS.md
arqux serve    # exposes governance over MCP (stdio)
```

```text
OUT-MIN workspace=./.arqux governor=anonymous workspace.init ok
```

Verified on a clean machine: `pip install arqux` currently publishes the 0.9.x line on PyPI — this repository already runs 1.0.x.

Your agent joins by reading the governance contract — not by guessing:

```bash
opencode --instructions "$(cat AGENTS.md)"
```

## What 1.0 does

| Capability | Verifiable fact |
|---|---|
| Governance over MCP | 115 handlers: session, cycle, blueprint, evidence, identity, timelog |
| Identity contracts | 7 identities with explicit axioms and limits; `arqux wake --identity` delivers state and rules in <1500 tokens (REQ-08) |
| CORTEX memory | Canonical format byte-exact certified in 5 runtimes |
| Sealed integrity | `seal.cortex` with per-artifact SHA-256; `arqux cortex-verify` detects tampering (REQ-03) |
| Multi-harness | `sync-harnesses` projects to `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.opencode/`; `drift-check` detects manual edits (REQ-07) |
| Exportable evidence | `evidence export` packages spans into `bundle.cortex`; `policy sign/verify` signs pure Ed25519 (REQ-11, REQ-12) |
| Authoritative journal | `push-delta`/`pull-policy` with deterministic ordering and `ERR_CONFLICT_VERSION` on conflict (REQ-13) |
| Measured quality | 2920 tests in the suite |

## Supported agents

- **Level 1 — files (universal):** any agent that can read `AGENTS.md` and write `.cortex`.
- **Level 2 — MCP (full):** any Model Context Protocol client.

Codex, OpenCode, Gemini CLI, z.ai, Qwen, Devin: they share no runtime or model — they share `.arqux/`.

## Documentation

| If you came to… | Start at |
|---|---|
| Evaluate the product | [`../README.md`](../README.md) — English documentation portal (canonical ES: [`../../es/README.md`](../../es/README.md)) |
| Learn by doing | [`../tutorial/inicio-rapido.md`](../tutorial/inicio-rapido.md) |
| Look up CLI, errors, configuration, formats | [`../referencia/`](../referencia/) |
| Read the CORTEX specification (ES, source corpus) | [`../../es/especificacion/`](../../es/especificacion/) |
| Audit evidence and compliance | [`EVIDENCE.md`](EVIDENCE.md) · [`../../es/guias/evidencia-y-cumplimiento.md`](../../es/guias/evidencia-y-cumplimiento.md) |
| See the full MCP surface | [`../../../HANDLERS.md`](../../../HANDLERS.md) |
| Understand the architecture and the whys | [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`../explicacion/`](../explicacion/) |

## Security · Contributing · License

- Vulnerability reporting: [`SECURITY.md`](SECURITY.md)
- How to contribute: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **Apache-2.0** license: [`../../../LICENSE`](../../../LICENSE)

---

**⬡ ArqUX** — Audit. Replay. Query.

```text
The file is the protocol.
The Q is the journal.
Your data stays on your ground.
```

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
