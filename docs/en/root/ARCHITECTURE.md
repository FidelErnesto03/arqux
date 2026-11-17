---
doc_type: explanation
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
<p align="center"><sub>Explanation · Informative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# ArqUX architecture

English twin of the canonical [`ARCHITECTURE.md`](../../../ARCHITECTURE.md).

> Document version: 1.0.0 — every layer and dependency named exists in `src/arqux/` and `pyproject.toml` today.

ArqUX is a governance layer for teams of AI agents. It sits between the user, the agent, the model and the workspace, and delivers identity contracts, MCP handlers, Blueprint lifecycle, CORTEX memory and verifiable evidence.

---

## 1. Layer view

```text
┌─────────────────────────────────────────────────────────┐
│                  User / Operator                         │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│                 CLI (click) — src/arqux/cli.py           │
│  init | status | call | serve | quickstart | doctor |    │
│  sync-harnesses | drift-check | wake | review |          │
│  evidence export | policy sign/verify | push-delta |     │
│  pull-policy | cortex-verify | backup | restore          │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│         MCP Server (stdio) — src/arqux/server.py         │
│  Exposes 115 handlers via Model Context Protocol         │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Handler Registry — src/arqux/handlers/ (18 modules) │
│  blueprint 16 · cortex 23 · session 9 · loop 9 · task 8  │
│  cycle 6 · protocol 5 · project 5 · timelog 5 · issue 4  │
│  identity 4 · evidence 3 · workspace 3 · context 2 ·     │
│  handler 2 · sync 2 · setup 1 · skill 8                  │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Permissions + Policy                                │
│  permissions.py — 3 roles (GOVERNOR/EXECUTOR/AUDITOR),   │
│  MUTATING_HANDLERS, HMAC_REQUIRED, ARQUX_STRICT_*        │
│  core/policy_engine.py — enforce:CODE|PROMPT|HUMAN       │
│  (CODE rules run as pre-write hooks; REQ-10)             │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      State — src/arqux/cortex/ + core/state              │
│  codec-cortex boundary (>=1.0,<1.1) fail-closed:         │
│  strict parser + atomic transactional write +            │
│  post-write guard with rollback (no codec → error)       │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Security + Journal + Evidence                       │
│  security.py — HMAC-SHA256 + $INTEGRITY (sha256)         │
│  signing.py — pure Ed25519 RFC 8032 (REQ-12)             │
│  journal.py — total ordering + ERR_CONFLICT_VERSION      │
│  evidence_export.py — signed bundle.cortex (REQ-11)      │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Institutional memory — src/arqux/memory/            │
│  native learning engine: authority | events | feedback | │
│  models | rebuild | recall | store (Apache-2.0)          │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│         Filesystem — .arqux/                             │
│  meta-brain.cortex | brain.cortex | projects.cortex |    │
│  identities/ | skills/ | templates/ | timelog/ | cycles/ │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Components

### 2.1 CLI (`src/arqux/cli.py`)

Click interface. The 1.0.0 surface groups:

- **Workspace/project:** `init`, `status`, `quickstart`, `doctor`, `project`, `cycle`, `validate`, `migrate`, `cortex-migrate`, `backup`, `restore`
- **Direct handler access:** `call <handler>` (any handler without MCP), `handlers` (lists the 115), `cortex-verify` (SHA-256 integrity), `elevate`, `identity`, `skill`
- **M2 — multi-harness ergonomics:** `sync-harnesses` projects `.arqux/` to `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `.opencode/instructions.md` with a common `source_hash`; `drift-check` detects manual edits (REQ-07). `wake --identity <role>` emits a <1500-token CORTEX payload with state, rules and active task (REQ-08). `review --cycle <id>` recompiles the cycle to HCORTEX with `loss_count == 0` (REQ-09).
- **M3 — platform/compliance:** `evidence export` packages execution spans into `bundle.cortex` with `--redact-private` by default (REQ-11). `policy keygen|sign|verify` signs pure Ed25519 with no new dependencies (REQ-12). `push-delta`/`pull-policy` sync against the authoritative journal with optimistic locking (REQ-13).
- **Servers:** `serve` (MCP core stdio), `serve-plantuml`, `session-bridge`, `loop-watch`, `comms-serve`, `voice-serve`, `voice-daemon`.

### 2.2 MCP Server (`src/arqux/server.py`)

Exposes the 115 handlers over stdio (Model Context Protocol). Each handler validates its `input_schema` (jsonschema) and returns `CortexOUT` — parseable text output (`OUT-WORK`/`OUT-ERROR`/`OUT-MIN`). Clients: any harness that speaks MCP.

### 2.3 Handler Registry (`src/arqux/handlers/`)

A single `REGISTRY` mapping handler name to spec (function + JSON Schema + description). 18 modules, 115 handlers — the live registry is the canonical source of the count (verified by `scripts/check_surfaces.py`).

### 2.4 Permissions (`src/arqux/permissions.py`)

Three-role model:

| Role | Identity | Access |
|---|---|---|
| **GOVERNOR** | Alfred | All handlers |
| **EXECUTOR** | Jarvis | Everything except `workspace.init`/`project.init` |
| **AUDITOR** | Heimdall, Seshat | Read-only — `MUTATING_HANDLERS` denied |

`HMAC_REQUIRED` handlers demand verified identity before executing. `ARQUX_STRICT_ROLES=1` forces the role check; `ARQUX_STRICT_SECURITY=1` forces HMAC verification.

### 2.5 Policy engine (`src/arqux/core/policy_engine.py`)

Policy rules with mandatory `enforce` level: `CODE` (executable pre-write hook), `PROMPT` (context injection) or `HUMAN` (approval). Missing level → `ERR_MISSING_ENFORCE_LEVEL` (REQ-10).

### 2.6 State (`src/arqux/cortex/` + `core/state/`)

Persistence in `.cortex` files (entries by `$N` sigil, validated). The boundary with **codec-cortex** (`>=1.0,<1.1`, core dependency since 1.0.0) is **fail-closed**: strict parse, sections resolved before mutating, atomic write with rollback and post-write verification — if the codec is missing, the write aborts with `RuntimeError`, it never writes unvalidated. Full detail in `../explicacion/frontera-codec.md`.

### 2.7 Security (`security.py`, `signing.py`, `journal.py`, `evidence_export.py`)

- **HMAC-SHA256** (`security.py`): identity verification bound to `agent_id|handler|timestamp|payload_hash` (anti-replay). Secrets in `.arqux/secrets/`, mode 0600.
- **SHA-256 integrity**: `$INTEGRITY` header per file; `arqux cortex-verify` detects tampering. Cycle close emits `seal.cortex` with per-artifact hash + tree root (REQ-03).
- **Pure Ed25519** (`signing.py`, REQ-12): `SIGNATURE_VALID` or `ERR_INVALID_SIGNATURE`, no external dependency. The `crypto` extra only covers the legacy `security.py` API.
- **Authoritative journal** (`journal.py`, REQ-13): disjoint deltas order deterministically; conflict on the same base → `ERR_CONFLICT_VERSION`.
- **Evidence export** (`evidence_export.py`, REQ-11): `bundle.cortex` with identity, skill, files, timestamps and SHA-256; a `visibility:"private"` field without `--allow-raw` blocks the export (`EXPORT_BLOCKED`).

### 2.8 Memory (`src/arqux/memory/`)

Native learning engine (Apache-2.0): `authority` (learning permissions), `events`, `feedback`, `models`, `rebuild`, `recall`, `store`. Three elevation levels: behavioral lesson → contextual knowledge → procedural skill.

### 2.9 Extensions (outside the core)

- `comms/` — Telegram bridge as a separate MCP stdio server (`comms-serve`), `comms` extra.
- `voice/` — local voice participation (faster-whisper STT + Piper/Kokoro TTS + Silero VAD), separate server and daemon, `voice` extra.
- `plantuml` — diagram rendering (`serve-plantuml`, `render-diagram`, `setup-plantuml`).

---

## 3. 1.0.0 data flow

### 3.1 Handler invocation

```text
arqux call blueprint.create obj="X" cycle=CYCLE-01
  │
  ▼  cli.py — resolves handler, parses key=value, PermissionContext.from_env()
handlers/blueprint.py:create
  │  1. enforce_ctx(ctx, "blueprint.create")   — role + HMAC if applicable
  │  2. policy gate (policy_engine)            — enforce:CODE rules
  │  3. validates input_schema + state (cycle with mature MANIFEST)
  ▼
cortex/ transactional write
  │  strict parse → AST mutation → codec verification → atomic write
  │  (fail-closed: error → rollback, nothing left half-written)
  ▼
evidence + sync
  │  event in brain PULSE (session/timelog) → meta-brain if applicable
  ▼
CortexOUT → click.echo → exit 0
```

### 3.2 Seal and journal

```text
cycle.close
  │  generates seal.cortex: SHA-256 per artifact + tree root
  ▼
push-delta
  │  packages a signable delta against the authoritative journal
  │  same base modified → ERR_CONFLICT_VERSION (optimistic locking)
  ▼
pull-policy — fetches consolidated policy in total order
```

---

## 4. Dependencies (pyproject.toml, verified)

**Core (5):**

| Dependency | Pin | Function |
|---|---|---|
| `mcp` | `>=1.0.0,<2` | MCP runtime (pin <2: server.py uses lowlevel decorators) |
| `codec-cortex` | `>=1.0,<1.1` | CORTEX/HCORTEX codec — verify/render/REQ-04/REQ-09 |
| `jsonschema` | `>=4.20` | `input_schema` validation in server.py |
| `click` | `>=8.1.0` | CLI |
| `rich` | `>=13.0.0` | Terminal output / dashboard |

**Extras:**

| Extra | Contents | For |
|---|---|---|
| `crypto` | `cryptography>=41` | Legacy `security.py` API (REQ-12 does not need it) |
| `voice` | faster-whisper, kokoro-onnx, piper-tts, onnxruntime, numpy, onnx-asr, huggingface-hub | Local voice extension |
| `comms` | `httpx>=0.24` | Telegram bridge |
| `dev` | pytest, pytest-asyncio | Development |

> `pydantic` left the core in 1.0.0 (arrives transitively via `mcp`).

---

## 5. `.arqux/` layout

```text
<workspace>/
├── AGENTS.md                     # entry contract — every agent reads it
└── .arqux/
    ├── meta-brain.cortex         # workspace memory (project registry)
    ├── projects.cortex           # project index
    ├── learn-policies.cortex     # learning-engine policies
    ├── identities/               # 7 identity contracts (.cortex) — workspace only
    ├── secrets/                  # HMAC keys (mode 0600)
    ├── skills/                   # skill definitions + workflows
    ├── templates/                # BLP_TEMPLATE, CYCLE_MANIFEST_TEMPLATE…
    ├── timelog/                  # SESxxx_<ts>.cortex — activity blocks
    └── packages/

<workspace>/<project>/.arqux/
    ├── brain.cortex              # project's governed memory
    ├── issues/                   # project issues
    └── cycles/
        └── CYCLE-NN/
            ├── MANIFEST.md       # cycle governing document
            ├── cycle.cortex
            └── blueprints/
                └── BLP-NNN.md    # 18-section decision document
```

---

## 6. References

- [`README.md`](README.md) — product door
- [`../referencia/cli.md`](../referencia/cli.md) — exhaustive CLI reference
- [`PERMISSIONS.md`](PERMISSIONS.md) — per-handler permission, generated from the registry
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — threat model
- [`EVIDENCE.md`](EVIDENCE.md) — evidence model
- [`../explicacion/frontera-codec.md`](../explicacion/frontera-codec.md) — the codec-cortex boundary
- [`../referencia/configuracion.md`](../referencia/configuracion.md) — env vars and paths
- `../../../HANDLERS.md` — the 115 handlers with signature and permission (generated, ES canonical)

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
