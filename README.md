# Arqux

> Minimum-viable governance framework for AI agent teams.
> Defines what to do, who does it, and leaves evidence — without slowing work down.

[![Status](https://img.shields.io/badge/status-beta-orange)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

---

## What is this?

Arqux is a governance framework for AI agents that work in teams. It is **not** an orchestrator, a CI/CD system, or a project manager. It is the **minimum viable protocol** that lets multiple agents collaborate on the same workspace without stepping on each other:

- A **governor** decides what to do and assigns it.
- An **executor** picks up the work and leaves evidence.
- An **auditor** can read everything but mutate nothing.

Every state mutation flows through a small set of MCP handlers. There is no direct file editing of governance state — handlers are the interface, files are the storage.

## ⚠️ This package uses a placeholder name

The directory you are looking at ships with the placeholder token `arqux` everywhere the final product name should appear. Before using the package, **run the rename script**:

```bash
python scripts/rename-product.py <chosen-name>
# Example:
python scripts/rename-product.py kyber
```

The script will:

1. Replace `arqux` → `kyber` (lowercase, used for package, CLI, paths)
2. Replace `ARQUX` → `KYBER` (constants, workspace markers)
3. Replace `Arqux` → `Kyber` (display names in docs)
4. Rename directories and files containing the placeholder.
5. Print a summary of every change.

Run with `--dry-run` first to preview the diff:

```bash
python scripts/rename-product.py kyber --dry-run
```

After rename, the framework is fully functional and ready for `pip install -e .`.

## Quick start

```bash
# 1. (After rename) install in editable mode
pip install -e .

# 2. Initialize a workspace
arqux init

# 3. Start the MCP server
arqux serve

# 4. Configure your MCP client (Gemini / Qwen / Claude / VS Code / Cursor) with one JSON line:
#    {
#      "mcpServers": {
#        "arqux": {
#          "command": "arqux",
#          "args": ["serve"]
#        }
#      }
#    }
```

## Why Arqux?

Two earlier frameworks tried to solve this from opposite angles:

| | Deep governance framework | Pragmatic MCP framework |
|---|---|---|
| Strength | Structure, identities, dual learning, CODEC-CORTEX | Fast iteration, MCP-native, low friction |
| Weakness | Too heavy: 100+ handlers, excessive ceremony | Too shallow: no org learning, weak governance |

Arqux takes the **conceptual skeleton** of the first (identities, dual learning, CODEC-CORTEX) and the **nervous system** of the second (native MCP, standby-first, incremental loading). The result is a single new product — not a fork, not a merge.

## Foundational principles (non-negotiable)

1. **Zero ceremony.** If a governance operation requires more than one handler invocation by the agent, the design is wrong.
2. **Self-contained.** `AGENTS.md` is the single entry point. No auxiliary reading required.
3. **Installable.** `pip install arqux`. No bash scripts, no absolute paths.
4. **Dogfooded.** The framework governs its own development from day one.
5. **State via CODEC-CORTEX.** All governance state is persisted through CODEC-CORTEX. No YAML, no JSON, no binary blobs.
6. **CODEC-CORTEX as codec.** Integrated as a natural dependency — no fork, no wrapper, no coupling.
7. **CORTEX-OUT for output efficiency.** Token minimization protocol on agent responses.
8. **Identities with teeth.** Permissions are enforced at the handler level — the system rejects, not just documents.
9. **Frictionless traceability.** Every governance action leaves an automatic trail.
10. **Clean exit.** Decommissioning an agent is one handler. No orphans.
11. **MCP as the only governance interface.** Direct editing of governance files is forbidden.
12. **Reversible governance.** Agents can suspend (`pause`) or fully detach (`off`) without losing state.

## Architecture at a glance

```
workspace/
├── .arqux/                  ← workspace-level governance
│   ├── meta-brain.cortex(.md)          ← level 1 brain: cross-project knowledge
│   └── projects.cortex(.md)            ← project index
│
├── my-project/
│   ├── .arqux/              ← project-level governance
│   │   ├── brain.cortex(.md)           ← level 2 brain: project context
│   │   ├── cycles/CYCLE-01/
│   │   │   ├── tasks/T-001.cortex(.md)
│   │   │   └── pulse.jsonl             ← append-only trace
│   │   └── evidence/
│   │
│   └── src/                            ← code (not governed)
│
└── [installed package]/
    └── agents/                         ← level 3 brains: identity-scoped
        ├── governor.cortex
        ├── executor.cortex
        └── auditor.cortex
```

**24 handlers, 6 modules:**

| Module | Handlers |
|---|---|
| `workspace` | `init`, `status`, `lessons` |
| `project` | `init`, `bind`, `unbind`, `status`, `lessons` |
| `cycle` | `create`, `list`, `current`, `close` |
| `task` | `create`, `claim`, `update`, `complete`, `fail`, `read`, `list` |
| `evidence` | `record`, `list`, `read` |
| `protocol` | `adopt`, `release`, `pause`, `resume` |

**3 roles:**

| Role | Can | Cannot |
|---|---|---|
| `governor` | Create cycles/tasks, assign, approve, close | Execute tasks |
| `executor` | Claim tasks, update progress, complete, fail | Create cycles/tasks |
| `auditor` | Read everything | Mutate anything |

## Repository layout

```
arqux/
├── README.md                    ← you are here
├── AGENTS.md                    ← single entry point for agents
├── CHANGELOG.md
├── LICENSE                      ← MIT
├── pyproject.toml               ← installable package
├── src/arqux/
│   ├── cli.py                   ← `arqux serve | init | status`
│   ├── server.py                ← MCP server
│   ├── cortex_out.py            ← CORTEX-OUT output profiles
│   ├── permissions.py           ← role enforcement middleware
│   ├── state.py                 ← state persistence helpers
│   ├── constants.py             ← ARQUX_* constants
│   ├── handlers/                ← 6 modules × 4 handlers
│   ├── identities/              ← 3 identity .cortex files
│   └── templates/               ← task/brain/meta-brain templates
├── tests/                       ← pytest suite
├── skills/                      ← lightweight on-demand skills
├── scripts/
│   ├── rename-product.py        ← placeholder → real name
│   └── rename-product.sh        ← thin wrapper
├── .arqux/           ← dogfooding: this repo governs itself
└── templates_root/              ← project skeleton templates
```

## Documentation

- **`AGENTS.md`** — single entry point. An agent that reads this file can operate.
- **`CHANGELOG.md`** — generated from `evidence.list` (per dogfooding rule).
- **`skills/README.md`** — describes the on-demand skill format.
- **`scripts/rename-product.py --help`** — placeholder replacement help.

## Development

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src tests
mypy src

# Run MCP server locally for testing
python -m arqux serve
```

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

Arqux synthesizes lessons from two earlier frameworks (NOMOS, DIALECT) and builds on the [CODEC-CORTEX](https://github.com/FidelErnesto03/codec-cortex) information codec. It is a new product, not a fork of either.
