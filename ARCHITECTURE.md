# Architecture

> **Document version:** 1.0 (2026-07-12)
> **ArqUX version:** 0.4.3+

This document describes the architecture of ArqUX, its layers, components, and data flow.

---

## 1. Overview

ArqUX is a governance framework for AI agent teams. It sits between the user, the agent, the model, and the workspace, providing identity contracts, MCP handlers, Blueprint lifecycle, CORTEX memory, and verifiable evidence.

```
┌─────────────────────────────────────────────────────────┐
│                     User / Operator                      │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│                    CLI (click)                           │
│  arqux init | status | call | cortex-verify | backup    │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│              MCP Server (stdio / SSE)                    │
│  Exposes 73 handlers via Model Context Protocol         │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│         Handler Registry (73 handlers, 12 modules)       │
│  blueprint | cortex | cycle | evidence | identity |      │
│  project | protocol | session | setup | skill | task |   │
│  workspace                                               │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Permissions Layer (Role-based access control)       │
│  GOVERNOR (full) | EXECUTOR (no init) | AUDITOR (read)   │
│  HMAC_REQUIRED for identity.record, evidence.record,     │
│  blueprint.approve, blueprint.re_delegate                │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      State Layer (CODEC-CORTEX persistence)              │
│  core/state/ — _brain, _crud, _migrate, _parse,          │
│                _project, _render                          │
│  File format: .cortex (sigil-based, validated)           │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Security Layer (HMAC + SHA-256 + Ed25519)           │
│  security.py — sign_request, verify_request,             │
│                hash_cortex, verify_cortex, sign_cortex   │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│         Filesystem (.arqux/ directory)                   │
│  meta-brain.cortex | brain.cortex | agents.cortex        │
│  identities/ | secrets/ | skills/ | cycles/              │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Layers

### 2.1 CLI Layer (`src/arqux/cli.py`)

Click-based command-line interface. Commands:

- `arqux init` — initialize `.arqux/` workspace
- `arqux status` — workspace/project/cycle status
- `arqux call <handler>` — invoke any handler directly (no MCP required)
- `arqux cortex-verify <path>` — verify SHA-256 integrity of a .cortex file
- `arqux doctor [--fix]` — diagnose and optionally repair workspace health
- `arqux backup` / `arqux restore` — timestamped backup with sha256 integrity
- `arqux migrate` — inject ARQX:artifact metadata
- `arqux validate` — validate .cortex structure
- `arqux elevate` — elevate a lesson via the unified motor
- `arqux identity {resolve, elevate, list}` — manage agent identities
- `arqux skill {import, list, resolve}` — manage skills with provenance
- `arqux handlers` — list all 73 handlers
- `arqux serve` — start MCP server on stdio
- `arqux setup-plantuml` / `arqux serve-plantuml` — PlantUML integration

### 2.2 MCP Server Layer (`src/arqux/server.py`)

Exposes the 73 handlers via Model Context Protocol. Supports stdio transport (default) and SSE transport. Each handler is invoked with a JSON input schema and returns a `CortexOUT` (text-based, parseable) response.

### 2.3 Handler Registry (`src/arqux/handlers/__init__.py`)

Single `REGISTRY: dict[str, HandlerSpec]` mapping handler names to their specs. Each spec contains:
- `name`: canonical dotted name (e.g. `blueprint.approve`)
- `fn`: Python callable
- `description`: human-readable
- `input_schema`: JSON Schema for parameters

**24-handler governance budget**: 24 handlers manage governance artifacts (blueprints, cycles, tasks, evidence, identities, sessions, projects, protocols). The remaining 49 are utility/read operations.

### 2.4 Permissions Layer (`src/arqux/permissions.py`)

Three-role model:
- **GOVERNOR** (Alfred): full access to all handlers
- **EXECUTOR** (Jarvis): universal access except `workspace.init` and `project.init`
- **AUDITOR** (Heimdall, Seshat): strictly read-only — denied all `MUTATING_HANDLERS`

HMAC_REQUIRED handlers require verified identity before execution:
- `identity.record`, `evidence.record`, `blueprint.approve`, `blueprint.re_delegate`

Environment variables:
- `ARQUX_STRICT_ROLES=1` — enforce role checks (default: legacy governor bypass)
- `ARQUX_STRICT_SECURITY=1` — enforce HMAC verification

### 2.5 State Layer (`src/arqux/core/state/`)

CODEC-CORTEX based persistence. Submodules:
- `_brain.py` — brain.cortex read/write, section helpers, concurrency bumping
- `_crud.py` — CRUD operations on .cortex entries (add, update, delete, move, list)
- `_migrate.py` — legacy metadata migration to ARQX:artifact format
- `_parse.py` — brain section parsing and rebuilding
- `_project.py` — workspace/project root discovery (`find_workspace_root`, `find_project_root`)
- `_render.py` — CORTEX/HCORTEX rendering

File format: `.cortex` files contain sigil-based entries (`$0` glossary, `$1` identity, `$2` focus, etc.) validated by codec-cortex.

### 2.6 Security Layer (`src/arqux/security.py`)

Three security primitives:
- **HMAC-SHA256** (`sign_request`, `verify_request`) — agent identity verification. Binds signature to `agent_id|handler|timestamp|payload_hash` to prevent replay and substitution.
- **SHA-256 integrity** (`hash_cortex`, `inject_hash_header`, `verify_cortex`) — file-level tamper detection via `$INTEGRITY` header.
- **Ed25519 signing** (`sign_cortex`, `verify_cortex_signature`) — optional non-repudiation for high-assurance scenarios.

Secret store: `.arqux/secrets/<agent>.key` files, mode 0600.

### 2.7 Filesystem Layout

```
<workspace>/
├── AGENTS.md
├── .arqux/
│   ├── meta-brain.cortex       # $1 META-BRAIN, $2 PROJECTS, $3 FOCUS, $4 AGENTS, $5 KNOWLEDGE
│   ├── brain.cortex            # project-level brain (per project)
│   ├── agents.cortex           # agent onboarding log
│   ├── projects.cortex         # projects index
│   ├── learn-policies.cortex   # learning engine policies
│   ├── identities/             # agent identity contracts (.cortex)
│   ├── secrets/                # HMAC secrets (mode 0600)
│   ├── skills/                 # skill definitions + workflows
│   ├── templates/              # BLP_TEMPLATE, CYCLE_MANIFEST_TEMPLATE, etc.
│   └── cycles/
│       └── CYCLE-NN/
│           ├── cycle.cortex
│           ├── cycle.md
│           ├── MANIFEST.md
│           └── blueprints/
│               └── BLP-NNN.md  # Blueprint files (18 sections)
```

---

## 3. Data Flow

### 3.1 Handler invocation (CLI)

```
User runs: arqux call blueprint.create obj="X" cycle=CYCLE-01
  │
  ▼
cli.py:_call_handler
  │ - resolve handler name (underscore → dot)
  │ - parse key=value args
  │ - load PermissionContext.from_env()
  ▼
handlers/blueprint/manage.py:create
  │ - enforce_ctx(ctx, "blueprint.create")
  │ - validate inputs
  │ - generate BLP-NNN ID via concurrency.next_blueprint_id_safe
  │ - write BLP-NNN.md from BLP_TEMPLATE.md
  ▼
core/state/_crud.py:crud_add (brain.cortex PULSE entry)
  │ - parse .cortex
  │ - mutate AST (add entry)
  │ - validate
  │ - atomic write
  │ - P1-P: auto-sign with $INTEGRITY header
  ▼
sync.py:sync_brain
  │ - update $8/WRK:current in brain.cortex
  │ - update $2/DOM:arqux in meta-brain.cortex (if metrics provided)
  ▼
Return CortexOUT → cli.py → click.echo → exit 0
```

### 3.2 HMAC verification flow

```
Agent calls: identity.record lesson="..." kind="behavioral"
  │
  ▼
handlers/identity.py:record
  │ - ctx.require_verified("identity.record")
  │   - if ARQUX_STRICT_SECURITY=1:
  │     - load secret from .arqux/secrets/<agent>.key
  │     - recompute HMAC: sha256(agent_id|handler|timestamp|payload_hash)
  │     - hmac.compare_digest(expected, signature)
  │     - if mismatch → IdentityVerificationError
  │ - proceed with handler
  ▼
Return CortexOUT
```

### 3.3 Tamper detection flow

```
User runs: arqux cortex-verify .arqux/brain.cortex
  │
  ▼
security.py:verify_cortex
  │ - read file
  │ - extract $INTEGRITY header (sha256:<hex>)
  │ - strip $INTEGRITY header from content
  │ - recompute sha256(stripped_content)
  │ - if hash != header_hash → TamperError
  ▼
cli.py:cmd_cortex_verify
  │ - exit 0 (OK) or exit 1 (FAIL)
```

---

## 4. Component Dependencies

```
arqux
├── codec-cortex >= 0.5.0    # CORTEX format parsing/validation
├── mcp >= 1.0.0             # Model Context Protocol server
├── pydantic >= 2.0.0        # Data validation
├── click >= 8.1.0           # CLI framework
├── rich >= 13.0.0           # Terminal output (dashboard)
└── cryptography (optional)  # Ed25519 signing (auto-installed)
```

---

## 5. Refactoring History

| Version | Refactor |
|---------|----------|
| 0.4.0 | Added security.py, concurrency.py, Role enum |
| 0.4.1 | Refactored handlers to packages (blueprint/, cortex/) |
| 0.4.2 | Refactored state.py → core/state/, learning.py → core/learning/ |
| 0.4.3 | P0-A/B/C/D/E/F fixes, P1-A-U fixes, MUTATING_HANDLERS frozenset, cortex-verify CLI, auto-signing |

---

## 6. References

- [AGENTS.md](AGENTS.md) — agent entry point
- [HANDLERS.md](HANDLERS.md) — full handler list
- [PERMISSIONS.md](PERMISSIONS.md) — permissions model
- [SECURITY.md](SECURITY.md) — security policy
- [THREAT_MODEL.md](THREAT_MODEL.md) — threat model
- [EVIDENCE.md](EVIDENCE.md) — evidence model
- [PILOT_MODE.md](PILOT_MODE.md) — pilot deployment guide
- [docs/architecture/diagrams/](docs/architecture/diagrams/) — PUML diagrams
