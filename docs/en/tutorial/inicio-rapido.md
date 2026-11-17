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
<p align="center"><sub>Tutorial · Informative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Quick start — your first governed workspace in ~10 minutes

*English translation — canonical source: `docs/es/tutorial/inicio-rapido.md`*

You will build an ArqUX workspace from scratch: install the package, initialize governance, register a project with its first cycle and blueprint, and connect a real agent over MCP. At the end, the agent answers questions it can only know by reading the project brain.

## What you need

- Python 3.10+ and ~10 minutes.
- An MCP client (Claude Desktop in the example; any stdio client works).
- Linux or macOS — commands verified on Linux (arqux 0.9.0 from PyPI; this repo already runs 1.0.x).

## Step 1 — Install ArqUX

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install arqux
```

You will see:

```text
Successfully installed arqux-0.9.0
```

## Step 2 — Initialize the workspace

```bash
mkdir mi-workspace && cd mi-workspace
arqux init
```

You will see:

```text
OUT-MIN workspace=./.arqux governor=anonymous workspace.init ok
```

You just created two things: `AGENTS.md` at the root — the governance contract every agent reads first — and `.arqux/` with `meta-brain.cortex` (workspace memory), `projects.cortex` (registry), `identities/` (7 role contracts) and `skills/`. No server, no API key: a directory.

> Optional: `export ARQUX_AGENT_ID=alfred` pins the operator identity (`governor=Alfred` in the output). The *agent's* identity comes from its reading of `AGENTS.md`, not this variable.

## Step 3 — Register a project

```bash
mkdir mi-proyecto && cd mi-proyecto
arqux project init name=mi-proyecto
```

The command prints the brain-seeding instructions and ends by creating `.arqux/brain.cortex` — the project's governed memory.

## Step 4 — Create the first cycle and its manifest

```bash
arqux cycle create name=CICLO-01
```

You will see:

```text
OUT-WORK cycle_id=CYCLE-01 status=draft ... cycle.create ok id=CYCLE-01 status=draft
```

The cycle is born in `draft`: the template manifest demands real content before hosting blueprints. Fill it in with one call:

```bash
arqux call cycle.synthesize cycle_id=CYCLE-01 content='$1:{Purpose: validate the governed flow end to end.} $2:{Inside: first cycle and test blueprint. Outside: real work.} $3:{Goal: one blueprint created under governance.} $4:{Rule: writes only via handlers.} $5:{Checkpoints: create cycle, create blueprint. Dates: today.} $6:{Index of cycle blueprints.} $7:{Status: test. Metrics: blueprints created.} $8:{Rule: mutations only via handlers. Rule: close with evidence.} $9:{Quality: real verified outputs.}'
```

You will see:

```text
OUT-WORK cycle_id=CYCLE-01 sections_written=1,2,3,4,5,6,7,8,9 cycle.synthesize ok
```

## Step 5 — Create the first blueprint

```bash
arqux call blueprint.create obj="First test blueprint"
```

You will see:

```text
OUT-WORK blueprint_id=BLP-001 cycle=CYCLE-01 status=draft markers=BLP:TITLE,BLP:1,...,BLP:18 blueprint.create ok
```

The blueprint is an 18-section decision document at `.arqux/cycles/CYCLE-01/blueprints/BLP-001.md` — it exists before anything executes. That is the central idea: architecture is thought before it mutates.

## Step 6 — Connect an agent over MCP

`arqux serve` exposes the 115 governance handlers over stdio. Add the server to your client:

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

**Any stdio client** — equivalent to launching:

```bash
cd mi-workspace && arqux serve
```

The server resolves `.arqux/` by walking up directories from its working directory — launch it with the workspace as cwd.

## Step 7 — Governed verification

Restart the client and ask the agent something it **can only know from the brain**:

> What project lives in this workspace, which cycle is open and which blueprint exists?

The agent queries the handlers (`project.status`, `cycle.current`, `blueprint.list`) and answers: project `mi-proyecto`, cycle `CYCLE-01`, blueprint `BLP-001` in draft. That answer is the proof: real context, not guessing.

## It worked if…

- [ ] `arqux init` created `AGENTS.md` and `.arqux/` (exit 0)
- [ ] `arqux project init` created `.arqux/brain.cortex` in the project
- [ ] `cycle.synthesize` returned `sections_written=1..9`
- [ ] `blueprint.create` returned `blueprint_id=BLP-001`
- [ ] The MCP client lists `arqux` tools and the agent answers with brain data

## What you just learned

- Governance is a directory: `AGENTS.md` + `.arqux/`, no server, no SDK.
- Work is thought before it executes: cycle → manifest → blueprint.
- The agent does not guess: it reads the contract and queries MCP handlers.

## Where to go next

| If you are… | Continue with |
|---|---|
| Exact command reference | [`../referencia/cli.md`](../referencia/cli.md) |
| Error contract | [`../referencia/errores.md`](../referencia/errores.md) |
| Configuration (env vars, paths, permissions) | [`../referencia/configuracion.md`](../referencia/configuracion.md) |
| CORTEX format specification | [`../especificacion/`](../especificacion/) |
| Architecture and decisions | [`ARCHITECTURE.md`](../../../ARCHITECTURE.md) · [`../explicacion/`](../explicacion/) |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
