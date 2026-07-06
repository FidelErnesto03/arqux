# Arqux

> Minimum-viable governance framework for AI agent teams.
> Defines what to do, who does it, and leaves evidence — without slowing work down.

[![Status](https://img.shields.io/badge/status-beta-orange)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()

---

## What is this?

Arqux is a governance framework for AI agents that work in teams. It is **not** an orchestrator, a CI/CD system, or a project manager. It is the **minimum viable protocol** that lets multiple agents collaborate on the same workspace without stepping on each other:

- A **governor** decides what to do and assigns it.
- An **executor** picks up the work and leaves evidence.
- An **auditor** can read everything but mutate nothing.

Every state mutation flows through MCP handlers. There is no direct file editing of governance state — handlers are the interface, files are the storage.

**Requires [CODEC-CORTEX](https://github.com/FidelErnesto03/codec-cortex) >= 0.4.0** — the canonical persistence codec. All state files use CORTEX sigil format with `$0` glossary.

---

## Quick start

```bash
# 1. Install
uv tool install -e .

# 2. Initialize a workspace
export ARQUX_AGENT_ID=alfred
export ARQUX_AGENT_ROLE=governor
arqux init

# 3. Configure MCP (Hermes example)
hermes mcp add arqux \
  --command arqux \
  --args serve \
  --env ARQUX_AGENT_ID=alfred \
  --env ARQUX_AGENT_ROLE=governor

# 4. Test
hermes mcp test arqux
# Expected: 38 tools discovered, 0 errors
```

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
- **originals_preserved**: External skills are stored in `skills/originals/` for backup. Only the CORTEX-converted version is used.

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
│   │   ├── originals/               ← external canon preserved
│   │   └── adaptations/             ← skill deviations (ADA)
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
   → converts to CORTEX ultra-dense in .arqux/skills/

3. Agent uses the skill (loaded from .arqux/skills/)
   → deviations recorded via skill.record()

4. skill.evolve(name, adaptation_id, apply=true)
   → updates the skill with approved adaptations
```

## Foundational principles (non-negotiable)

1. **Zero ceremony.** If a governance operation requires more than one handler invocation by the agent, the design is wrong.
2. **Self-contained.** `AGENTS.md` is the single entry point. No auxiliary reading required.
3. **Installable.** `uv tool install -e .` or eventually `pip install arqux`.
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
# Install in editable mode
uv tool install -e .

# Run tests
uv pip install pytest pytest-asyncio
PYTHONPATH=src python3 -m pytest tests/

# Run MCP server locally
ARQUX_AGENT_ID=alfred ARQUX_AGENT_ROLE=governor arqux serve
```

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

Arqux synthesizes lessons from two earlier frameworks (NOMOS, DIALECT) and builds on the [CODEC-CORTEX](https://github.com/FidelErnesto03/codec-cortex) information codec. It is a new product, not a fork of either.
