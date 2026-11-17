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
<p align="center"><sub>Guide · Informative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Deploying ArqUX in your environment

*English translation — canonical source: `docs/es/guias/despliegue.md`*

Deployment and operations guide for version **1.0.0**. Replaces `PILOT_MODE.md` (retired — it described the 0.4.x line). Every value stated here was verified against `pyproject.toml`, the source code and real measurements.

## Choose your deployment mode

| Mode | What it is | When to choose it |
|---|---|---|
| **Standalone local** | `arqux` CLI on a repo; governance in `.arqux/` | A human (or script) operates governance directly |
| **MCP server** | `arqux serve` exposes 115 handlers over stdio | An agent (Claude, Cursor, opencode) needs governed handlers |
| **Shared multi-harness** | MCP + `sync-harnesses` projects `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`; team-shared journal | Several agents/people work on the same workspace |

Modes accumulate: a typical team deploys standalone + MCP + harness projection.

## Prerequisites and extras

Common prerequisites (all three modes):

- Python ≥ 3.11
- `pip install arqux` — installs the published PyPI line (as of this guide, **0.9.0**; this repo's 1.0.0 is not yet on PyPI). To deploy 1.0.0 today: `pip install -e .` from the repo.

Runtime dependencies (declared in `pyproject.toml`):

- `mcp>=1.0.0,<2` — MCP server (deliberate pin: `server.py` uses the lowlevel API)
- `codec-cortex>=1.0,<1.1` — CORTEX/HCORTEX codec (1.0.x line, boundary pin)
- `jsonschema>=4.20`, `click>=8.1.0`, `rich>=13.0.0`

Optional extras:

- `pip install "arqux[crypto]"` — `cryptography>=41` only for the legacy `arqux.security` API. `arqux policy sign/verify` uses pure-Python Ed25519 and does **not** need it.
- `pip install "arqux[voice]"` — local voice pipeline (faster-whisper + Piper/Kokoro + Silero VAD). Not required for governance.
- `pip install "arqux[dev]"` — development toolchain (pytest, ruff, mypy, pre-commit).

## Deployment by mode

### 1. Standalone local

```bash
pip install -e .            # or pip install arqux for the PyPI line
cd my-repo
arqux init                  # creates .arqux/ + AGENTS.md — ~0.2s
```

`.arqux/` is the product's only state: brain, blueprints, journal, identities, policies. Deleting `.arqux/` = uninstalling governance (project files stay intact).

### 2. MCP server for agents

```bash
arqux serve                 # stdio, one workspace per process
```

Register the server in the MCP client (same pattern everywhere):

```json
{"mcpServers": {"arqux": {"command": "arqux", "args": ["serve"], "cwd": "/path/to/workspace"}}}
```

A `tools/list` must return the 115 handlers. If the agent identifies itself, export `ARQUX_AGENT_ID` (see env table) before launching the client.

### 3. Shared multi-harness

```bash
arqux sync-harnesses        # generates AGENTS.md, CLAUDE.md, GEMINI.md, .opencode/instructions.md
arqux drift-check           # verifies projections were not hand-edited
arqux pull-policy           # pulls the team journal
arqux push-delta            # publishes your deltas
```

Ritual details in [Team sync](sincronizar-equipo.md) and [Projecting governance](proyectar-agentes.md).

## Environment variables

Deployment-relevant vars (grep-verified against `src/arqux/`) — the exhaustive list lives in [Configuration](../referencia/configuracion.md):

| Variable | Purpose | Default |
|---|---|---|
| `ARQUX_DIR` | Governed state root | `.arqux/` in cwd |
| `ARQUX_AGENT_ID` | Calling agent's identity | anonymous (warning at init) |
| `ARQUX_AGENT_ROLE` | Role: `GOVERNOR` / `EXECUTOR` / `AUDITOR` | `EXECUTOR` |
| `ARQUX_AGENT_SECRET` | HMAC secret for signed handlers | empty (signing disabled) |
| `ARQUX_AGENT_SIGNATURE`, `ARQUX_AGENT_TIMESTAMP` | Call signature+ts (HMAC handlers) | — |
| `ARQUX_EXECUTION_KEY` | Execution elevation key | — |
| `ARQUX_STRICT_ROLES` | Denies undeclared roles | off |
| `ARQUX_STRICT_SECURITY` | Security surface hardening | off |
| `ARQUX_STRICT_EXECUTION` | Strict blueprint execution | off |
| `ARQUX_ALLOW_IMPLICIT_EXECUTION` | Allows context-implied executor | off |
| `ARQUX_COMMS_EGRESS` | Comms bridge egress | off |
| `ARQUX_COMMS_ALLOWLIST` | Comms destination allowlist | — |
| `ARQUX_COMMS_TELEGRAM_TOKEN` | Telegram bot token (bridge) | — |

Per-scenario detail in [Configuration](../referencia/configuracion.md).

## Shared journal (honest topology)

The journal (`journal.cortex`) is the workspace's append-only evidence. There is no built-in server: transport is **file-based** — the team shares it through whatever medium it already uses (git repo, shared mount, CI artifact).

- `arqux push-delta` packages your deltas; `arqux pull-policy` applies the team's.
- Concurrent version conflict → `ERR_CONFLICT_VERSION`; resolution documented in [Team sync](sincronizar-equipo.md).
- The journal is verifiable offline — the chain audits without an ArqUX server.

## Hardening

Minimum production checklist:

- [ ] `.arqux/keys/` (if signing material exists): `chmod 700`, keys `chmod 600`
- [ ] `ARQUX_AGENT_SECRET` in a secrets manager — **never** in the repo or `AGENTS.md`
- [ ] `.gitignore`: `.arqux/keys/`, `*.secret`, venvs; the rest of `.arqux/` **is** versioned (it is the evidence)
- [ ] `ARQUX_STRICT_ROLES=1` and `ARQUX_STRICT_SECURITY=1` in multi-agent environments
- [ ] Journal backup: it is a flat file — include `.arqux/journal.cortex` in the repo backup
- [ ] Dependency pinning in production (`codec-cortex>=1.0,<1.1` already bounded)

## Measured performance

Measured on this development machine (Linux, Python 3.11, modest CPU — treat as a range, not a contract):

| Operation | Measurement |
|---|---|
| `arqux --version` | ~0.16 s |
| `arqux wake` | ~0.2 s (serializes+renders brain) |
| `arqux init` | <1 s |
| Full `pytest` suite | 2,920 tests, ~1–2 min depending on machine |

The product is I/O over flat `.cortex` files: the dominant cost is parsing the brain, which grows with its size — `cortex.gc` and periodic compaction keep it bounded.

## Go-live checklist

- [ ] `arqux doctor` green on the workspace
- [ ] `tools/list` returns 115 handlers from the MCP client
- [ ] `ARQUX_AGENT_ID`/role exported per agent
- [ ] `sync-harnesses` run + `drift-check` green
- [ ] Journal included in backup; keys outside the repo
- [ ] `pytest tests/e2e/test_docs_contract.py` green (honest docs)

## See also

- [Boot an agent](arranque-agente.md) — the per-role `arqux wake` ritual
- [Audit the work](auditar-trabajo.md) — reviewing what was deployed
- [ARCHITECTURE.md](../../../ARCHITECTURE.md) — product internals

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
