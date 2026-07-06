# ArqUX

> Minimum-viable governance framework for AI agent teams.
> Defines what to do, who does it, and leaves evidence — without slowing work down.

[![Status](https://img.shields.io/badge/status-beta-orange)]()
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()

---

## What is this?

Arqux is a **governance framework + learning engine + skill ecosystem** for AI agent teams. It is built on [CODEC-CORTEX](https://github.com/FidelErnesto03/codec-cortex), the canonical information codec that compresses structured knowledge into ultra-dense, self-indexing CORTEX sigil format.

Arqux enables three layers of learning:
- **Behavioral** — Agent identities evolve through `identity.record()`.
- **Contextual** — Project lessons are scanned, scored, and elevated to permanent knowledge via `cortex.learn`.
- **Procedural** — External skills are imported, converted to CORTEX, used by agents, and evolved through adaptations.

It is **not** an orchestrator, a CI/CD system, or a project manager. It is the **minimum viable protocol** that lets multiple agents collaborate on the same workspace without stepping on each other:

- A **governor** decides what to do and assigns it.
- An **executor** picks up the work and leaves evidence.
- An **auditor** can read everything but mutate nothing.

Every state mutation flows through 38 MCP handlers. There is no direct file editing of governance state — handlers are the interface, files are the storage in canonical CODEC-CORTEX format.

**Requires [CODEC-CORTEX](https://github.com/FidelErnesto03/codec-cortex) >= 0.4.0.**

---

## Quick start

```bash
# 1. Install from PyPI (once published)
pip install arqux
# Or via uv:
# uv tool install arqux

# 2. Set agent environment (required for all arqux commands)
export ARQUX_AGENT_ID=alfred
export ARQUX_AGENT_ROLE=governor

# 3. Initialize a governed workspace
mkdir ~/my-workspace && cd ~/my-workspace
arqux init
# Creates: AGENTS.md + .arqux/ (manifest, brain, meta-brain, identities, skills)

# 4. Start the MCP server (in a separate terminal or background)
arqux serve
```

**5. Configure MCP client.** Arqux exposes 38 tools via the Model Context Protocol. Add the following to your MCP client configuration (replace `<path-to-arqux>` with `which arqux`):

```json
{
  "mcpServers": {
    "arqux": {
      "command": "<path-to-arqux>",
      "args": ["serve"],
      "env": {
        "ARQUX_AGENT_ID": "alfred",
        "ARQUX_AGENT_ROLE": "governor"
      }
    }
  }
}
```

**6. Verify connectivity.** Most MCP clients provide a test mechanism:

- **Hermes:** `hermes mcp test arqux`
- **Claude Desktop:** check the MCP tools panel
- **VS Code:** check the MCP extension output

Expected: 38 tools discovered, 0 errors.

**7. Restart or reload** the MCP session so tools become available (most clients: reload tools or restart the app).

> **Development install** (from repo): `git clone ... && cd arqux && uv tool install --force -e .`
>
> **Note:** If the MCP client discovers the tools but they don't appear in the session, reload or restart the client. The `arqux serve` process runs the code version that was current when it started — after reinstalling, restart the server.

## Core concepts

### Three learning layers

| Layer | What it captures | Where | Mechanism |
|---|---|---|---|
| **Behavioral** | Agent identity, style, axioms | `.arqux/identities/<agent>.cortex` | `identity.record()` |
| **Contextual** | Project lessons → knowledge | `brain.cortex` §7 → §10 | `cortex.learn` (scan → elevate) |
| **Procedural** | Skills and capabilities | `.arqux/skills/*.skill.md` | `skill.import → convert → record → evolve` |

### Two language rules

| Rule | Scope | Language |
|---|---|---|
| `AXM:natural_language` | Human-facing responses | Working context (currently Spanish) |
| `AXM:agent_lang_en` | Agent artifacts (AGENTS.md, skills, state files) | English |

### Canonical rules

- **context_first**: Read `brain.cortex` before any `ls`/`find`/`cat`. The brain is the source of truth.
- **standby_first**: Every session starts with an open question to the Architect.
- **workflows_govern_operations**: Load `workflows.skill.md` before any multi-step operation.
- **skills_under_governance**: All skills used by agents MUST be in `.arqux/skills/` in CORTEX format.
- **adaptations_in_skill**: ADA entries are stored in the skill file itself (`$0: ADAPTATIONS`), not in separate files. The skill is self-contained.

## Architecture at a glance

```
workspace/
├── AGENTS.md                        ← single entry point for agents (CORTEX in .md)
├── .arqux/
│   ├── manifest.cortex
│   ├── brain.cortex                 ← workspace-level brain
│   ├── meta-brain.cortex            ← cross-project knowledge
│   ├── projects.cortex              ← registered project index
│   ├── identities/ (7)              ← Alfred, Jarvis, Seshat, Heimdall + roles
│   ├── skills/                      ← CORTEX skills (loaded on demand)
│   │   └── originals/               ← external canon preserved
│   ├── cycles/                      ← workspace cycles
│   └── packages/                    ← supplemental .cortex packages
│
└── my-project/
    └── .arqux/
        ├── brain.cortex             ← 12 sections: FCS, OBJ, KNW, LNG, RSK...
        ├── cycles/CYCLE-01/
        │   └── tasks/T-001.cortex
        ├── packages/                ← project-specific packages
        └── learn-policies.cortex    ← learning engine thresholds
```

## Handlers (38 total)

### Governance (24 handlers)

| Module | Handlers |
|---|---|
| `workspace` | `init`, `status`, `lessons` |
| `project` | `init(name, path?, seed?)`, `bind`, `unbind`, `status`, `lessons` |
| `cycle` | `create`, `list`, `current`, `close` |
| `task` | `create`, `claim`, `update`, `complete`, `fail`, `read`, `list` |
| `evidence` | `record`, `list`, `read` |
| `protocol` | `adopt`, `release`, `pause`, `resume` |

### Utility (14 handlers)

| Module | Handlers |
|---|---|
| `cortex` | `read`, `write`, `verify`, `render` |
| `cortex.learn` | `learn` (scan), `learn.elevate` (dry-run or apply) |
| `identity` | `record` (behavioral lesson) |
| `skill` | `import`, `convert`, `record`, `evolve`, `list` |

## Skill lifecycle

```
1. skill.import(source, name, content)
   → stores original in .arqux/skills/originals/

2. skill.convert(name)
   → converts to CORTEX with $0: ADAPTATIONS section

3. Agent uses the skill (loaded from .arqux/skills/)
   → deviations recorded via skill.record() → appended to $0: ADAPTATIONS

4. skill.evolve(name, adaptation_id, apply=true)
   → marks the ADA as applied (status → "applied") in $0
   → entry preserved for history, skill self-contained
```

## Foundational principles (non-negotiable)

1. **Zero ceremony.** If a governance operation requires more than one handler invocation by the agent, the design is wrong.
2. **Self-contained.** `AGENTS.md` is the single entry point. No auxiliary reading required.
3. **Installable.** `pip install arqux` (development: `uv tool install --force -e .`).
4. **Dogfooded.** The framework governs its own development from day one.
5. **State via CODEC-CORTEX.** All governance state uses CORTEX sigil format with `$0` glossary. Attrs single-line, cuerpo multiline.
6. **CODEC-CORTEX as codec.** Natural dependency — no fork, no wrapper.
7. **CORTEX-OUT for output efficiency.** Token minimization protocol on agent responses.
8. **Identities with teeth.** Permissions enforced at the handler level.
9. **Frictionless traceability.** Every governance action leaves an automatic trail.
10. **Clean exit.** Decommissioning an agent is one handler. No orphans.
11. **MCP as the only governance interface.** Direct editing of governance files is forbidden.
12. **SKILL-driven procedure.** Skills are external, convertible to CORTEX, and evolve by use — the canon never changes.

## Three roles

| Role | Can | Cannot |
|---|---|---|
| `governor` | Create cycles/tasks, assign, approve, close | Execute tasks |
| `executor` | Claim tasks, update progress, complete, fail | Create cycles/tasks, mutate workspace |
| `auditor` | Read everything | Mutate anything |

## Repository layout

```
arqux/
├── README.md
├── AGENTS.md                    ← single entry point for agents (CORTEX)
├── pyproject.toml
├── src/arqux/
│   ├── cli.py                   ← `arqux init | serve`
│   ├── server.py                ← MCP server
│   ├── cortex_out.py            ← CORTEX-OUT output profiles
│   ├── permissions.py           ← role enforcement
│   ├── constants.py
│   ├── state.py                 ← core: brain read/write, CODEC-CORTEX init
│   ├── pulse.py                 ← pulse/evidence operations
│   ├── sessions.py              ← session add/release
│   ├── formats.py               ← canonical CORTEX builder
│   ├── learning.py              ← CODEC-CORTEX learning engine adapter
│   ├── handlers/
│   │   ├── __init__.py          ← registry (38 handlers)
│   │   ├── workspace.py
│   │   ├── project.py
│   │   ├── cycle.py
│   │   ├── task.py
│   │   ├── evidence.py
│   │   ├── protocol.py
│   │   ├── cortex.py            ← + identity.record + learn handlers
│   │   └── skill.py             ← skill lifecycle handlers
│   ├── identities/ (7)
│   ├── skills/ (10 .skill.md)
│   └── templates/
│       ├── AGENTS.md
│       └── learn-policies.cortex
├── tests/ (57+ tests)
└── .arqux/                      ← dogfooding: this repo governs itself
```

## Documentation

- **`AGENTS.md`** — single entry point. An agent that reads this file can operate under Arqux.
- **`.arqux/skills/workflows.skill.md`** — 7 canonical workflows with PlantUML diagrams.
- **`.arqux/skills/handlers.skill.md`** — full handler reference with examples.
- **`.arqux/skills/learning.skill.md`** — CODEC-CORTEX learning engine usage.
- **`.arqux/skills/format.skill.md`** — file conventions and canonical format rules.

## Development

```bash
# Install in editable mode (from repo clone)
uv tool install --force -e .

# Run tests
uv pip install pytest pytest-asyncio --python $(which python3)
PYTHONPATH=src python3 -m pytest tests/

# Run MCP server locally for testing
ARQUX_AGENT_ID=alfred ARQUX_AGENT_ROLE=governor python3 -m arqux serve
```

## License

Apache 2.0 — see [LICENSE](LICENSE).